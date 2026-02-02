"""
VRAM-Aware Job Queue

Manages generation jobs with:
- Single GPU lock (one heavy job at a time)
- Dependency resolution
- Progress streaming via WebSocket
- Cancellation support
"""

import asyncio
import os
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set
import uuid

from apps.video_editor.models import (
    Job,
    JobStatus,
    JobType,
    JobProgressEvent,
    TimelineClip,
    RegenerationMode,
    GeneratedAsset,
    GeneratorConfig,
)
from apps.video_editor.generators.base import (
    BaseGenerator,
    GeneratorRegistry,
    get_generator_registry,
    ProgressCallback,
    TTSGenerator,
    VideoGenerator,
    ImageGenerator,
    LLMGenerator,
)


# Type for WebSocket broadcast callback
BroadcastCallback = Callable[[str, Dict[str, Any]], Any]


@dataclass
class QueuedJob:
    """Internal representation of a queued job with runtime state."""
    job: Job
    project_id: str
    task: Optional[asyncio.Task] = None
    cancelled: bool = False
    broadcast: Optional[BroadcastCallback] = None
    seq: int = 0


class JobQueue:
    """
    VRAM-aware job queue for video generation.
    
    Features:
    - Single GPU lock: only one heavy job runs at a time
    - Lightweight jobs (LLM via API) can run concurrently
    - Dependency resolution: jobs wait for dependencies
    - Progress streaming with sequence numbers
    - Graceful cancellation
    """

    def __init__(self, vram_budget_gb: float = 24.0):
        self.vram_budget_gb = vram_budget_gb
        self.vram_in_use_gb = 0.0
        
        # Job storage by project
        self._jobs: Dict[str, Dict[str, QueuedJob]] = {}  # project_id -> job_id -> job
        
        # Queue state
        self._running_job_id: Optional[str] = None
        self._pending_queue: List[QueuedJob] = []
        
        # Locks
        self._gpu_lock = asyncio.Lock()
        self._queue_lock = asyncio.Lock()
        
        # Cancellation tokens
        self._cancel_events: Dict[str, asyncio.Event] = {}
        
        # Shutdown flag
        self._shutdown = False

    async def enqueue(
        self,
        project_id: str,
        job: Job,
        broadcast: Optional[BroadcastCallback] = None,
    ) -> str:
        """
        Enqueue a job for execution.
        
        Args:
            project_id: Project this job belongs to
            job: The job to enqueue
            broadcast: Callback for sending progress events
            
        Returns:
            Job ID
        """
        async with self._queue_lock:
            # Ensure job has an ID
            if not job.id:
                job.id = str(uuid.uuid4())
            
            # Create queued job
            queued = QueuedJob(
                job=job,
                project_id=project_id,
                broadcast=broadcast,
            )
            
            # Add to project jobs
            if project_id not in self._jobs:
                self._jobs[project_id] = {}
            self._jobs[project_id][job.id] = queued
            
            # Create cancel event
            self._cancel_events[job.id] = asyncio.Event()
            
            # Add to pending queue
            self._pending_queue.append(queued)
            job.status = JobStatus.QUEUED
            
            # Try to start next job
            asyncio.create_task(self._process_queue())
            
            return job.id

    async def cancel(self, job_id: str) -> bool:
        """
        Cancel a job.
        
        Args:
            job_id: ID of the job to cancel
            
        Returns:
            True if cancellation was requested
        """
        cancel_event = self._cancel_events.get(job_id)
        if cancel_event:
            cancel_event.set()
        
        # Find and mark the job
        for project_jobs in self._jobs.values():
            if job_id in project_jobs:
                queued = project_jobs[job_id]
                queued.cancelled = True
                queued.job.status = JobStatus.CANCELLED
                
                # Cancel the task if running
                if queued.task and not queued.task.done():
                    queued.task.cancel()
                
                return True
        
        return False

    async def get_job(self, project_id: str, job_id: str) -> Optional[Job]:
        """Get a job by ID."""
        project_jobs = self._jobs.get(project_id, {})
        queued = project_jobs.get(job_id)
        return queued.job if queued else None

    async def list_jobs(self, project_id: str) -> List[Job]:
        """List all jobs for a project."""
        project_jobs = self._jobs.get(project_id, {})
        return [q.job for q in project_jobs.values()]

    async def clear_completed(self, project_id: str) -> int:
        """
        Clear completed/cancelled/failed jobs for a project.
        
        Returns:
            Number of jobs cleared
        """
        async with self._queue_lock:
            project_jobs = self._jobs.get(project_id, {})
            to_remove = []
            
            for job_id, queued in project_jobs.items():
                if queued.job.status in (JobStatus.COMPLETED, JobStatus.CANCELLED, JobStatus.FAILED):
                    to_remove.append(job_id)
            
            for job_id in to_remove:
                del project_jobs[job_id]
                self._cancel_events.pop(job_id, None)
            
            return len(to_remove)

    async def _process_queue(self) -> None:
        """Process the pending queue and start eligible jobs."""
        if self._shutdown:
            return
        
        async with self._queue_lock:
            # Already running a heavy job?
            if self._running_job_id:
                return
            
            # Find next eligible job
            for i, queued in enumerate(self._pending_queue):
                if queued.cancelled:
                    continue
                
                # Check dependencies
                if not await self._dependencies_met(queued):
                    continue
                
                # Check VRAM
                vram_needed = queued.job.vram_gb_required
                if vram_needed > 0 and vram_needed > (self.vram_budget_gb - self.vram_in_use_gb):
                    continue
                
                # Start this job
                self._pending_queue.pop(i)
                self._running_job_id = queued.job.id
                self.vram_in_use_gb += vram_needed
                
                queued.task = asyncio.create_task(self._run_job(queued))
                break

    async def _dependencies_met(self, queued: QueuedJob) -> bool:
        """Check if all job dependencies are completed."""
        for dep_id in queued.job.depends_on:
            # Find the dependency job
            found = False
            for project_jobs in self._jobs.values():
                if dep_id in project_jobs:
                    dep_job = project_jobs[dep_id].job
                    if dep_job.status != JobStatus.COMPLETED:
                        return False
                    found = True
                    break
            
            if not found:
                # Dependency not found - assume it's complete or was removed
                pass
        
        return True

    async def _run_job(self, queued: QueuedJob) -> None:
        """Execute a job."""
        job = queued.job
        cancel_event = self._cancel_events.get(job.id)
        
        try:
            job.status = JobStatus.RUNNING
            job.started_at = datetime.now().timestamp()
            
            # Send start event
            await self._broadcast_progress(queued, JobProgressEvent(
                job_id=job.id,
                seq=self._next_seq(queued),
                stage="starting",
                stage_progress=0.0,
                overall_progress=0.0,
                message=f"Starting {job.type.value} job",
            ))
            
            # Execute based on job type
            if job.type == JobType.STORY_GENERATE:
                await self._run_story_job(queued, cancel_event)
            elif job.type == JobType.TTS_GENERATE:
                await self._run_tts_job(queued, cancel_event)
            elif job.type == JobType.IMAGE_GENERATE:
                await self._run_image_job(queued, cancel_event)
            elif job.type == JobType.VIDEO_GENERATE:
                await self._run_video_job(queued, cancel_event)
            elif job.type == JobType.MUSIC_GENERATE:
                await self._run_music_job(queued, cancel_event)
            elif job.type == JobType.FINAL_MERGE:
                await self._run_merge_job(queued, cancel_event)
            else:
                raise ValueError(f"Unknown job type: {job.type}")
            
            # Mark completed
            if not queued.cancelled:
                job.status = JobStatus.COMPLETED
                job.completed_at = datetime.now().timestamp()
                
                await self._broadcast_progress(queued, JobProgressEvent(
                    job_id=job.id,
                    seq=self._next_seq(queued),
                    stage="completed",
                    stage_progress=1.0,
                    overall_progress=1.0,
                    message="Job completed successfully",
                ))
        
        except asyncio.CancelledError:
            job.status = JobStatus.CANCELLED
            await self._broadcast_progress(queued, JobProgressEvent(
                job_id=job.id,
                seq=self._next_seq(queued),
                stage="cancelled",
                stage_progress=0.0,
                overall_progress=job.last_progress,
                message="Job was cancelled",
            ))
        
        except Exception as e:
            job.status = JobStatus.FAILED
            job.error_message = str(e)
            job.completed_at = datetime.now().timestamp()
            
            await self._broadcast_progress(queued, JobProgressEvent(
                job_id=job.id,
                seq=self._next_seq(queued),
                stage="error",
                stage_progress=0.0,
                overall_progress=job.last_progress,
                message=f"Job failed: {str(e)}",
            ))
        
        finally:
            # Release resources
            async with self._queue_lock:
                if self._running_job_id == job.id:
                    self._running_job_id = None
                    self.vram_in_use_gb = max(0, self.vram_in_use_gb - job.vram_gb_required)
            
            # Clean up cancel event
            self._cancel_events.pop(job.id, None)
            
            # Process next job
            asyncio.create_task(self._process_queue())

    def _next_seq(self, queued: QueuedJob) -> int:
        """Get next sequence number for a job."""
        queued.seq += 1
        queued.job.last_seq = queued.seq
        return queued.seq

    async def _broadcast_progress(
        self,
        queued: QueuedJob,
        event: JobProgressEvent
    ) -> None:
        """Broadcast a progress event."""
        queued.job.last_progress = event.overall_progress
        
        if queued.broadcast:
            try:
                await queued.broadcast(
                    "ve_job_progress",
                    {
                        "projectId": queued.project_id,
                        "event": event.model_dump(),
                    }
                )
            except Exception:
                pass  # Don't fail job on broadcast error

    def _make_progress_callback(
        self,
        queued: QueuedJob,
        stage: str,
        stage_weight: float = 1.0,
        stage_offset: float = 0.0,
    ) -> ProgressCallback:
        """Create a progress callback for a generation step."""
        async def callback(event: JobProgressEvent) -> None:
            # Adjust progress for this stage's weight
            event.stage = stage
            event.overall_progress = stage_offset + (event.stage_progress * stage_weight)
            await self._broadcast_progress(queued, event)
        
        return callback

    # ─────────────────────────────────────────────────────────────────────
    # Job Type Implementations (Placeholders for V1)
    # ─────────────────────────────────────────────────────────────────────

    async def _run_story_job(
        self,
        queued: QueuedJob,
        cancel_event: Optional[asyncio.Event]
    ) -> None:
        """Run story generation job (LLM-based)."""
        from apps.video_editor.project import get_video_project_manager
        
        job = queued.job
        manager = get_video_project_manager()
        project = manager.get_project(queued.project_id)
        
        if not project:
            raise RuntimeError("Project not found")
        
        # Get the LLM generator
        registry = get_generator_registry()
        generator_id = job.generator_id or "story_llm"
        
        gen_instance = registry.get_instance(generator_id)
        if not gen_instance:
            # Try to create instance
            gen_class = registry.get(generator_id)
            if gen_class:
                config = GeneratorConfig(custom=job.generator_config or {})
                gen_instance = gen_class(config)
                await gen_instance.load()
            else:
                raise RuntimeError(f"Generator not found: {generator_id}")
        
        # Create progress callback
        progress_cb = self._create_progress_callback(queued, "generating_story", 0.0, 1.0)
        
        if cancel_event and cancel_event.is_set():
            raise asyncio.CancelledError()
        
        # Get the topic/prompt from job spec
        topic = job.story_spec.get("topic", "") if job.story_spec else ""
        genre = job.story_spec.get("genre") if job.story_spec else None
        num_scenes = job.story_spec.get("num_scenes", 5) if job.story_spec else 5
        
        if hasattr(gen_instance, "generate_story"):
            # Use high-level story generation
            result = await gen_instance.generate_story(
                topic=topic,
                genre=genre,
                num_scenes=num_scenes,
                progress_callback=progress_cb,
            )
        else:
            # Fallback to basic generate
            result = await gen_instance.generate(
                prompt=topic,
                progress_callback=progress_cb,
            )
        
        if not result.get("success", False) and not getattr(result, "success", False):
            error = result.get("error") or getattr(result, "error", "Unknown error")
            raise RuntimeError(f"Story generation failed: {error}")
        
        # Extract story from result
        story_data = result.get("story") if isinstance(result, dict) else None
        if story_data:
            # Update project story with generated content
            from apps.video_editor.models import Story, StoryScene
            
            scenes = []
            for idx, scene_data in enumerate(story_data.get("scenes", [])):
                scenes.append(StoryScene(
                    id=str(uuid.uuid4()),
                    title=scene_data.get("title", f"Scene {idx + 1}"),
                    order=idx,
                    narration=scene_data.get("narration", ""),
                    visual_prompt=scene_data.get("visual_prompt", ""),
                    camera_notes=scene_data.get("camera_notes", ""),
                    duration_estimate=scene_data.get("duration_estimate", 5.0),
                ))
            
            new_story = Story(
                title=story_data.get("title", project.story.title),
                genre=story_data.get("genre", project.story.genre),
                synopsis=story_data.get("synopsis", ""),
                scenes=scenes,
                updated_at=datetime.now().timestamp(),
            )
            
            manager.update_story(queued.project_id, new_story)
        
        await self._broadcast_progress(queued, JobProgressEvent(
            job_id=job.id,
            seq=self._next_seq(queued),
            stage="completed",
            stage_progress=1.0,
            overall_progress=1.0,
            message="Story generation complete",
        ))

    async def _run_tts_job(
        self,
        queued: QueuedJob,
        cancel_event: Optional[asyncio.Event]
    ) -> None:
        """Run TTS generation job."""
        from apps.video_editor.project import get_video_project_manager
        
        job = queued.job
        manager = get_video_project_manager()
        project = manager.get_project(queued.project_id)
        
        if not project:
            raise RuntimeError("Project not found")
        
        # Get TTS generator
        registry = get_generator_registry()
        generator_id = job.generator_id or "tts_coqui_xtts"
        
        gen_instance = registry.get_instance(generator_id)
        if not gen_instance:
            gen_class = registry.get(generator_id)
            if gen_class:
                config = GeneratorConfig(custom=job.generator_config or {})
                gen_instance = gen_class(config)
                await gen_instance.load()
            else:
                raise RuntimeError(f"TTS generator not found: {generator_id}")
        
        # Get clips to process
        clips_to_process = []
        for clip in project.timeline.clips:
            if job.clip_ids and clip.id not in job.clip_ids:
                continue
            # Only process clips with narration
            scene = next((s for s in project.story.scenes if s.id == clip.scene_id), None)
            if scene and scene.narration:
                clips_to_process.append((clip, scene))
        
        if not clips_to_process:
            await self._broadcast_progress(queued, JobProgressEvent(
                job_id=job.id,
                seq=self._next_seq(queued),
                stage="skipped",
                stage_progress=1.0,
                overall_progress=1.0,
                message="No clips with narration to process",
            ))
            return
        
        total_clips = len(clips_to_process)
        
        # Get project asset directory
        assets_dir = Path(project.root_path) / "xeditor.video" / "assets" / "audio"
        assets_dir.mkdir(parents=True, exist_ok=True)
        
        for i, (clip, scene) in enumerate(clips_to_process):
            if cancel_event and cancel_event.is_set():
                raise asyncio.CancelledError()
            
            # Progress callback for this clip
            def create_clip_callback(clip_idx: int):
                async def cb(event: JobProgressEvent) -> None:
                    event.stage = f"generating_audio_{clip_idx + 1}"
                    event.overall_progress = (clip_idx + event.stage_progress) / total_clips
                    await self._broadcast_progress(queued, event)
                return cb
            
            output_path = str(assets_dir / f"{clip.id}.wav")
            
            # Get voice sample if available
            voice_sample_path = None
            if clip.voice_id:
                voice_asset = next((v for v in project.library.voices if v.id == clip.voice_id), None)
                if voice_asset and voice_asset.sample_path:
                    voice_sample_path = voice_asset.sample_path
            
            result = await gen_instance.generate(
                text=scene.narration,
                output_path=output_path,
                voice_sample_path=voice_sample_path,
                language=project.settings.language or "en",
                progress_callback=create_clip_callback(i),
            )
            
            if result.success:
                # Update clip with generated audio info
                clip.audio_artifact_path = output_path
                clip.duration = result.duration_seconds if result.duration_seconds else clip.duration
                clip.audio_generated_at = datetime.now().timestamp()
                
                # Add to generated assets
                gen_asset = GeneratedAsset(
                    id=str(uuid.uuid4()),
                    generator_id=generator_id,
                    artifact_type="audio",
                    artifact_path=output_path,
                    created_at=datetime.now().timestamp(),
                    metadata={"text": scene.narration, "duration": result.duration_seconds},
                )
                project.generated_assets.append(gen_asset)
            else:
                print(f"[TTS] Failed to generate audio for clip {clip.id}: {result.error}")
            
            await self._broadcast_progress(queued, JobProgressEvent(
                job_id=job.id,
                seq=self._next_seq(queued),
                stage="generating_audio",
                stage_progress=1.0,
                overall_progress=(i + 1) / total_clips,
                message=f"Generated audio {i + 1}/{total_clips}",
            ))
        
        # Save updated project
        manager._save_project_state(project)
        
        await self._broadcast_progress(queued, JobProgressEvent(
            job_id=job.id,
            seq=self._next_seq(queued),
            stage="completed",
            stage_progress=1.0,
            overall_progress=1.0,
            message="TTS generation complete",
        ))

    async def _run_image_job(
        self,
        queued: QueuedJob,
        cancel_event: Optional[asyncio.Event]
    ) -> None:
        """Run image generation job."""
        from apps.video_editor.project import get_video_project_manager
        
        job = queued.job
        manager = get_video_project_manager()
        project = manager.get_project(queued.project_id)
        
        if not project:
            raise RuntimeError("Project not found")
        
        # Get T2I generator
        registry = get_generator_registry()
        generator_id = job.generator_id or "t2i_sdxl"
        
        gen_instance = registry.get_instance(generator_id)
        if not gen_instance:
            gen_class = registry.get(generator_id)
            if gen_class:
                config = GeneratorConfig(custom=job.generator_config or {})
                gen_instance = gen_class(config)
                await gen_instance.load()
            else:
                raise RuntimeError(f"T2I generator not found: {generator_id}")
        
        # Get clips to process
        clips_to_process = []
        for clip in project.timeline.clips:
            if job.clip_ids and clip.id not in job.clip_ids:
                continue
            # Get visual prompt from scene
            scene = next((s for s in project.story.scenes if s.id == clip.scene_id), None)
            if scene and scene.visual_prompt:
                clips_to_process.append((clip, scene))
        
        if not clips_to_process:
            await self._broadcast_progress(queued, JobProgressEvent(
                job_id=job.id,
                seq=self._next_seq(queued),
                stage="skipped",
                stage_progress=1.0,
                overall_progress=1.0,
                message="No clips with visual prompts to process",
            ))
            return
        
        total_clips = len(clips_to_process)
        
        # Get project asset directory
        assets_dir = Path(project.root_path) / "xeditor.video" / "assets" / "images"
        assets_dir.mkdir(parents=True, exist_ok=True)
        
        # Resolution settings
        width = project.settings.resolution_width or 1024
        height = project.settings.resolution_height or 576
        
        for i, (clip, scene) in enumerate(clips_to_process):
            if cancel_event and cancel_event.is_set():
                raise asyncio.CancelledError()
            
            def create_clip_callback(clip_idx: int):
                async def cb(event: JobProgressEvent) -> None:
                    event.stage = f"generating_image_{clip_idx + 1}"
                    event.overall_progress = (clip_idx + event.stage_progress) / total_clips
                    await self._broadcast_progress(queued, event)
                return cb
            
            output_path = str(assets_dir / f"{clip.id}.png")
            
            # Build prompt with style info
            prompt = scene.visual_prompt
            if project.settings.visual_style:
                prompt = f"{prompt}, {project.settings.visual_style}"
            
            result = await gen_instance.generate(
                prompt=prompt,
                output_path=output_path,
                width=width,
                height=height,
                progress_callback=create_clip_callback(i),
            )
            
            if result.success:
                # Update clip with generated image info
                clip.image_artifact_path = output_path
                clip.image_generated_at = datetime.now().timestamp()
                
                # Add to generated assets
                gen_asset = GeneratedAsset(
                    id=str(uuid.uuid4()),
                    generator_id=generator_id,
                    artifact_type="image",
                    artifact_path=output_path,
                    created_at=datetime.now().timestamp(),
                    metadata={
                        "prompt": prompt,
                        "width": width,
                        "height": height,
                        "seed": result.seed,
                    },
                )
                project.generated_assets.append(gen_asset)
            else:
                print(f"[T2I] Failed to generate image for clip {clip.id}: {result.error}")
            
            await self._broadcast_progress(queued, JobProgressEvent(
                job_id=job.id,
                seq=self._next_seq(queued),
                stage="generating_image",
                stage_progress=1.0,
                overall_progress=(i + 1) / total_clips,
                message=f"Generated image {i + 1}/{total_clips}",
            ))
        
        # Save updated project
        manager._save_project_state(project)
        
        await self._broadcast_progress(queued, JobProgressEvent(
            job_id=job.id,
            seq=self._next_seq(queued),
            stage="completed",
            stage_progress=1.0,
            overall_progress=1.0,
            message="Image generation complete",
        ))

    async def _run_video_job(
        self,
        queued: QueuedJob,
        cancel_event: Optional[asyncio.Event]
    ) -> None:
        """Run video generation job."""
        from apps.video_editor.project import get_video_project_manager
        
        job = queued.job
        manager = get_video_project_manager()
        project = manager.get_project(queued.project_id)
        
        if not project:
            raise RuntimeError("Project not found")
        
        # Get video generator
        registry = get_generator_registry()
        # Default to slideshow for V1 - it's fast and always works
        generator_id = job.generator_id or "i2v_slideshow"
        
        gen_instance = registry.get_instance(generator_id)
        if not gen_instance:
            gen_class = registry.get(generator_id)
            if gen_class:
                config = GeneratorConfig(custom=job.generator_config or {})
                gen_instance = gen_class(config)
                await gen_instance.load()
            else:
                raise RuntimeError(f"Video generator not found: {generator_id}")
        
        # Get clips to process
        clips_to_process = []
        for clip in project.timeline.clips:
            if job.clip_ids and clip.id not in job.clip_ids:
                continue
            # Need either an image or a visual prompt
            scene = next((s for s in project.story.scenes if s.id == clip.scene_id), None)
            has_image = bool(clip.image_artifact_path) and os.path.exists(clip.image_artifact_path or "")
            has_prompt = scene and scene.visual_prompt
            if has_image or has_prompt:
                clips_to_process.append((clip, scene))
        
        if not clips_to_process:
            await self._broadcast_progress(queued, JobProgressEvent(
                job_id=job.id,
                seq=self._next_seq(queued),
                stage="skipped",
                stage_progress=1.0,
                overall_progress=1.0,
                message="No clips with images to process",
            ))
            return
        
        total_clips = len(clips_to_process)
        
        # Get project asset directory
        assets_dir = Path(project.root_path) / "xeditor.video" / "assets" / "video"
        assets_dir.mkdir(parents=True, exist_ok=True)
        
        # Video settings
        width = project.settings.resolution_width or 1024
        height = project.settings.resolution_height or 576
        fps = project.settings.fps or 30
        
        for i, (clip, scene) in enumerate(clips_to_process):
            if cancel_event and cancel_event.is_set():
                raise asyncio.CancelledError()
            
            def create_clip_callback(clip_idx: int):
                async def cb(event: JobProgressEvent) -> None:
                    event.stage = f"generating_video_{clip_idx + 1}"
                    event.overall_progress = (clip_idx + event.stage_progress) / total_clips
                    await self._broadcast_progress(queued, event)
                return cb
            
            output_path = str(assets_dir / f"{clip.id}.mp4")
            
            # Determine duration - use audio duration if available
            duration = clip.duration or 4.0
            
            # Build generation params
            gen_kwargs = {
                "output_path": output_path,
                "first_frame_path": clip.image_artifact_path,
                "duration_seconds": duration,
                "fps": fps,
                "width": width,
                "height": height,
                "progress_callback": create_clip_callback(i),
            }
            
            # Add prompts for T2V/I2V generators that use them
            if scene:
                gen_kwargs["prompt"] = scene.visual_prompt
                gen_kwargs["motion_prompt"] = scene.camera_notes
            
            result = await gen_instance.generate(**gen_kwargs)
            
            if result.success:
                # Update clip with generated video info
                clip.video_artifact_path = output_path
                clip.video_generated_at = datetime.now().timestamp()
                clip.status = "generated"
                
                # Update duration if generator reports it
                if result.duration_seconds:
                    clip.duration = result.duration_seconds
                
                # Add to generated assets
                gen_asset = GeneratedAsset(
                    id=str(uuid.uuid4()),
                    generator_id=generator_id,
                    artifact_type="video",
                    artifact_path=output_path,
                    created_at=datetime.now().timestamp(),
                    metadata={
                        "duration": result.duration_seconds,
                        "fps": result.fps,
                        "width": result.width,
                        "height": result.height,
                    },
                )
                project.generated_assets.append(gen_asset)
            else:
                print(f"[Video] Failed to generate video for clip {clip.id}: {result.error}")
            
            await self._broadcast_progress(queued, JobProgressEvent(
                job_id=job.id,
                seq=self._next_seq(queued),
                stage="generating_video",
                stage_progress=1.0,
                overall_progress=(i + 1) / total_clips,
                message=f"Generated video {i + 1}/{total_clips}",
            ))
        
        # Save updated project
        manager._save_project_state(project)
        
        await self._broadcast_progress(queued, JobProgressEvent(
            job_id=job.id,
            seq=self._next_seq(queued),
            stage="completed",
            stage_progress=1.0,
            overall_progress=1.0,
            message="Video generation complete",
        ))

    async def _run_music_job(
        self,
        queued: QueuedJob,
        cancel_event: Optional[asyncio.Event]
    ) -> None:
        """Run music generation job."""
        # Placeholder - will be implemented with music generator
        for i in range(20):
            if cancel_event and cancel_event.is_set():
                raise asyncio.CancelledError()
            
            await self._broadcast_progress(queued, JobProgressEvent(
                job_id=queued.job.id,
                seq=self._next_seq(queued),
                stage="generating_music",
                stage_progress=(i + 1) / 20,
                overall_progress=(i + 1) / 20,
                message=f"Generating music... {(i + 1) * 5}%",
            ))
            await asyncio.sleep(0.5)

    async def _run_merge_job(
        self,
        queued: QueuedJob,
        cancel_event: Optional[asyncio.Event]
    ) -> None:
        """Run final merge/export job using FFmpeg."""
        from apps.video_editor.project import get_video_project_manager
        
        job = queued.job
        manager = get_video_project_manager()
        project = manager.get_project(queued.project_id)
        
        if not project:
            raise RuntimeError("Project not found")
        
        # Get output directory
        renders_dir = Path(project.root_path) / "xeditor.video" / "renders"
        renders_dir.mkdir(parents=True, exist_ok=True)
        
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = str(renders_dir / f"{project.name}_{timestamp}.mp4")
        
        # Get clips sorted by order
        clips = sorted(project.timeline.clips, key=lambda c: c.start_time)
        
        if not clips:
            raise RuntimeError("No clips to merge")
        
        # Stage 1: Prepare clip list
        await self._broadcast_progress(queued, JobProgressEvent(
            job_id=job.id,
            seq=self._next_seq(queued),
            stage="preparing",
            stage_progress=0.5,
            overall_progress=0.1,
            message="Preparing clips for merge...",
        ))
        
        if cancel_event and cancel_event.is_set():
            raise asyncio.CancelledError()
        
        # Collect valid clips
        video_inputs = []
        audio_inputs = []
        
        for clip in clips:
            if clip.video_artifact_path and os.path.exists(clip.video_artifact_path):
                video_inputs.append({
                    "path": clip.video_artifact_path,
                    "duration": clip.duration,
                })
            if clip.audio_artifact_path and os.path.exists(clip.audio_artifact_path):
                audio_inputs.append({
                    "path": clip.audio_artifact_path,
                    "start_time": clip.start_time,
                })
        
        if not video_inputs:
            raise RuntimeError("No video clips to merge")
        
        # Stage 2: Create concat file
        await self._broadcast_progress(queued, JobProgressEvent(
            job_id=job.id,
            seq=self._next_seq(queued),
            stage="creating_concat",
            stage_progress=0.5,
            overall_progress=0.2,
            message="Creating concat list...",
        ))
        
        concat_file = renders_dir / f"concat_{timestamp}.txt"
        with open(concat_file, "w") as f:
            for video in video_inputs:
                # Escape quotes in path
                escaped_path = video["path"].replace("'", "'\\''")
                f.write(f"file '{escaped_path}'\n")
        
        if cancel_event and cancel_event.is_set():
            raise asyncio.CancelledError()
        
        # Stage 3: Merge videos
        await self._broadcast_progress(queued, JobProgressEvent(
            job_id=job.id,
            seq=self._next_seq(queued),
            stage="merging_video",
            stage_progress=0.5,
            overall_progress=0.4,
            message="Merging video clips...",
        ))
        
        temp_video = str(renders_dir / f"temp_video_{timestamp}.mp4")
        
        try:
            # Concat videos using FFmpeg
            cmd = [
                "ffmpeg", "-y",
                "-f", "concat",
                "-safe", "0",
                "-i", str(concat_file),
                "-c", "copy",
                temp_video
            ]
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,
            )
            
            if result.returncode != 0:
                print(f"[Merge] FFmpeg concat error: {result.stderr}")
                # Try with re-encoding if copy fails
                cmd = [
                    "ffmpeg", "-y",
                    "-f", "concat",
                    "-safe", "0",
                    "-i", str(concat_file),
                    "-c:v", "libx264",
                    "-preset", "medium",
                    "-crf", "23",
                    temp_video
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
                if result.returncode != 0:
                    raise RuntimeError(f"FFmpeg concat failed: {result.stderr}")
        
        except subprocess.TimeoutExpired:
            raise RuntimeError("FFmpeg concat timed out")
        
        if cancel_event and cancel_event.is_set():
            raise asyncio.CancelledError()
        
        # Stage 4: Add audio if available
        await self._broadcast_progress(queued, JobProgressEvent(
            job_id=job.id,
            seq=self._next_seq(queued),
            stage="merging_audio",
            stage_progress=0.5,
            overall_progress=0.6,
            message="Adding audio tracks...",
        ))
        
        final_output = output_path
        
        if audio_inputs:
            # Create complex filter for multiple audio streams
            audio_filter_inputs = []
            filter_parts = []
            
            for idx, audio in enumerate(audio_inputs):
                audio_filter_inputs.extend(["-i", audio["path"]])
                # adelay for positioning audio
                delay_ms = int(audio.get("start_time", 0) * 1000)
                filter_parts.append(f"[{idx + 1}:a]adelay={delay_ms}|{delay_ms}[a{idx}]")
            
            # Mix all audio streams
            audio_labels = "".join(f"[a{i}]" for i in range(len(audio_inputs)))
            filter_parts.append(f"{audio_labels}amix=inputs={len(audio_inputs)}:duration=longest[aout]")
            
            filter_complex = ";".join(filter_parts)
            
            try:
                cmd = [
                    "ffmpeg", "-y",
                    "-i", temp_video,
                    *audio_filter_inputs,
                    "-filter_complex", filter_complex,
                    "-map", "0:v",
                    "-map", "[aout]",
                    "-c:v", "copy",
                    "-c:a", "aac",
                    "-b:a", "192k",
                    final_output
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
                
                if result.returncode != 0:
                    print(f"[Merge] Audio merge warning: {result.stderr}")
                    # Fall back to video only
                    os.rename(temp_video, final_output)
                else:
                    # Clean up temp video
                    os.remove(temp_video)
                    
            except subprocess.TimeoutExpired:
                os.rename(temp_video, final_output)
        else:
            # No audio, just use the merged video
            os.rename(temp_video, final_output)
        
        # Clean up concat file
        try:
            os.remove(concat_file)
        except OSError:
            pass
        
        if cancel_event and cancel_event.is_set():
            raise asyncio.CancelledError()
        
        # Stage 5: Finalize
        await self._broadcast_progress(queued, JobProgressEvent(
            job_id=job.id,
            seq=self._next_seq(queued),
            stage="finalizing",
            stage_progress=1.0,
            overall_progress=0.9,
            message="Finalizing export...",
        ))
        
        # Update project with render info
        gen_asset = GeneratedAsset(
            id=str(uuid.uuid4()),
            generator_id="ffmpeg_merge",
            artifact_type="render",
            artifact_path=final_output,
            created_at=datetime.now().timestamp(),
            metadata={
                "num_clips": len(video_inputs),
                "has_audio": len(audio_inputs) > 0,
            },
        )
        project.generated_assets.append(gen_asset)
        manager._save_project_state(project)
        
        await self._broadcast_progress(queued, JobProgressEvent(
            job_id=job.id,
            seq=self._next_seq(queued),
            stage="completed",
            stage_progress=1.0,
            overall_progress=1.0,
            message=f"Export complete: {os.path.basename(final_output)}",
            artifact_path=final_output,
        ))

    async def shutdown(self) -> None:
        """Shutdown the job queue gracefully."""
        self._shutdown = True
        
        # Cancel all running/pending jobs
        for job_id, event in list(self._cancel_events.items()):
            event.set()
        
        # Wait for running tasks
        for project_jobs in self._jobs.values():
            for queued in project_jobs.values():
                if queued.task and not queued.task.done():
                    try:
                        await asyncio.wait_for(queued.task, timeout=5.0)
                    except (asyncio.TimeoutError, asyncio.CancelledError):
                        queued.task.cancel()


# Singleton instance
_job_queue: Optional[JobQueue] = None


def get_job_queue() -> JobQueue:
    """Get the singleton job queue."""
    global _job_queue
    if _job_queue is None:
        _job_queue = JobQueue()
    return _job_queue


# ─────────────────────────────────────────────────────────────────────────────
# RPC Handlers
# ─────────────────────────────────────────────────────────────────────────────

async def handle_ve_start_job(payload: Dict[str, Any], broadcast: Optional[BroadcastCallback] = None) -> Dict[str, Any]:
    """RPC handler for starting a generation job."""
    queue = get_job_queue()
    
    project_id = payload.get("projectId", "")
    job_type_str = payload.get("jobType", "")
    clip_ids = payload.get("clipIds", [])
    scene_ids = payload.get("sceneIds", [])
    generator_id = payload.get("generatorId")
    generator_config = payload.get("generatorConfig")
    regen_mode_str = payload.get("regenerationMode")
    story_spec = payload.get("storySpec")  # For story_generate jobs
    
    if not project_id:
        return {"success": False, "error": "Project ID is required"}
    if not job_type_str:
        return {"success": False, "error": "Job type is required"}
    
    try:
        job_type = JobType(job_type_str)
    except ValueError:
        return {"success": False, "error": f"Invalid job type: {job_type_str}"}
    
    # Create job
    job = Job(
        type=job_type,
        clip_ids=clip_ids,
        scene_ids=scene_ids,
        generator_id=generator_id,
        generator_config=generator_config,
        story_spec=story_spec,
    )
    
    # TODO: Calculate VRAM requirement based on generator
    job.vram_gb_required = 12.0  # Default for now
    
    # Enqueue
    job_id = await queue.enqueue(project_id, job, broadcast)
    
    return {
        "success": True,
        "jobId": job_id,
        "status": job.status.value,
    }


async def handle_ve_cancel_job(payload: Dict[str, Any]) -> Dict[str, Any]:
    """RPC handler for cancelling a job."""
    queue = get_job_queue()
    
    job_id = payload.get("jobId", "")
    
    if not job_id:
        return {"success": False, "error": "Job ID is required"}
    
    cancelled = await queue.cancel(job_id)
    return {"success": cancelled}


async def handle_ve_get_job(payload: Dict[str, Any]) -> Dict[str, Any]:
    """RPC handler for getting job status."""
    queue = get_job_queue()
    
    project_id = payload.get("projectId", "")
    job_id = payload.get("jobId", "")
    
    if not project_id or not job_id:
        return {"success": False, "error": "Project ID and Job ID are required"}
    
    job = await queue.get_job(project_id, job_id)
    if job:
        return {"success": True, "job": job.model_dump()}
    return {"success": False, "error": "Job not found"}


async def handle_ve_list_jobs(payload: Dict[str, Any]) -> Dict[str, Any]:
    """RPC handler for listing project jobs."""
    queue = get_job_queue()
    
    project_id = payload.get("projectId", "")
    
    if not project_id:
        return {"success": False, "error": "Project ID is required"}
    
    jobs = await queue.list_jobs(project_id)
    return {
        "success": True,
        "jobs": [j.model_dump() for j in jobs],
    }
