"""
VRAM-Aware Job Queue

Manages generation jobs with:
- Single GPU lock (one heavy job at a time)
- Dependency resolution
- Progress streaming via WebSocket
- Cancellation support
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Set
import uuid

from apps.video_editor.models import (
    Job,
    JobStatus,
    JobType,
    JobProgressEvent,
    TimelineClip,
    RegenerationMode,
)
from apps.video_editor.generators.base import (
    BaseGenerator,
    GeneratorRegistry,
    get_generator_registry,
    ProgressCallback,
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
        # This will be implemented when we add the LLM bridge generator
        # For now, just simulate progress
        for i in range(10):
            if cancel_event and cancel_event.is_set():
                raise asyncio.CancelledError()
            
            await self._broadcast_progress(queued, JobProgressEvent(
                job_id=queued.job.id,
                seq=self._next_seq(queued),
                stage="generating_story",
                stage_progress=(i + 1) / 10,
                overall_progress=(i + 1) / 10,
                message=f"Generating story... {(i + 1) * 10}%",
            ))
            await asyncio.sleep(0.5)

    async def _run_tts_job(
        self,
        queued: QueuedJob,
        cancel_event: Optional[asyncio.Event]
    ) -> None:
        """Run TTS generation job."""
        # Placeholder - will be implemented with TTS generator
        job = queued.job
        total_clips = len(job.clip_ids) or 1
        
        for i in range(total_clips):
            if cancel_event and cancel_event.is_set():
                raise asyncio.CancelledError()
            
            await self._broadcast_progress(queued, JobProgressEvent(
                job_id=job.id,
                seq=self._next_seq(queued),
                stage="generating_audio",
                stage_progress=(i + 1) / total_clips,
                overall_progress=(i + 1) / total_clips,
                message=f"Generating audio {i + 1}/{total_clips}",
            ))
            await asyncio.sleep(1.0)

    async def _run_image_job(
        self,
        queued: QueuedJob,
        cancel_event: Optional[asyncio.Event]
    ) -> None:
        """Run image generation job."""
        # Placeholder - will be implemented with T2I generator
        job = queued.job
        total_clips = len(job.clip_ids) or 1
        
        for i in range(total_clips):
            if cancel_event and cancel_event.is_set():
                raise asyncio.CancelledError()
            
            await self._broadcast_progress(queued, JobProgressEvent(
                job_id=job.id,
                seq=self._next_seq(queued),
                stage="generating_image",
                stage_progress=(i + 1) / total_clips,
                overall_progress=(i + 1) / total_clips,
                message=f"Generating image {i + 1}/{total_clips}",
            ))
            await asyncio.sleep(2.0)

    async def _run_video_job(
        self,
        queued: QueuedJob,
        cancel_event: Optional[asyncio.Event]
    ) -> None:
        """Run video generation job."""
        # Placeholder - will be implemented with video generator
        job = queued.job
        total_clips = len(job.clip_ids) or 1
        
        for i in range(total_clips):
            if cancel_event and cancel_event.is_set():
                raise asyncio.CancelledError()
            
            # Simulate frame-by-frame progress
            total_frames = 120
            for frame in range(total_frames):
                if cancel_event and cancel_event.is_set():
                    raise asyncio.CancelledError()
                
                clip_progress = (frame + 1) / total_frames
                overall = (i + clip_progress) / total_clips
                
                await self._broadcast_progress(queued, JobProgressEvent(
                    job_id=job.id,
                    seq=self._next_seq(queued),
                    stage="generating_video",
                    stage_progress=clip_progress,
                    overall_progress=overall,
                    current_frame=frame + 1,
                    total_frames=total_frames,
                    message=f"Generating video {i + 1}/{total_clips} - frame {frame + 1}/{total_frames}",
                ))
                await asyncio.sleep(0.05)

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
        """Run final merge/export job."""
        # Placeholder - will be implemented with FFmpeg
        stages = ["preparing", "merging_video", "merging_audio", "encoding", "finalizing"]
        
        for i, stage in enumerate(stages):
            if cancel_event and cancel_event.is_set():
                raise asyncio.CancelledError()
            
            await self._broadcast_progress(queued, JobProgressEvent(
                job_id=queued.job.id,
                seq=self._next_seq(queued),
                stage=stage,
                stage_progress=1.0,
                overall_progress=(i + 1) / len(stages),
                message=f"Final export: {stage}",
            ))
            await asyncio.sleep(1.0)

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
