"""
Audio-First Scene → Clip Planner

Implements the deterministic planning algorithm:
1. For each scene, compute total audio duration
2. Pick video generator → get max_duration_seconds
3. Split scene into N = ceil(audio_duration / max_clip) video clips
4. Set continuity links (clip k>0 links first frame from prev clip's last)
5. Create SceneInstance groupings binding video + audio clips

Also handles:
- Ripple operations (move/resize with downstream shift)
- Staleness propagation
- Re-planning when generator changes (different max duration)
"""

import math
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from apps.video_editor.models import (
    ClipSourceType,
    ClipStatus,
    ClipRef,
    GenerationMode,
    GenerationSpec,
    GeneratorCapabilities,
    GeneratorType,
    SceneInstance,
    StoryScene,
    Timeline,
    TimelineClip,
    TimelineTrack,
    TrackType,
    VideoProject,
)
from apps.video_editor.generators.base import (
    GeneratorRegistry,
    get_generator_registry,
)


# ─────────────────────────────────────────────────────────────────────────────
# Core planner
# ─────────────────────────────────────────────────────────────────────────────

def plan_scene_clips(
    scene: StoryScene,
    audio_duration: float,
    video_generator_caps: GeneratorCapabilities,
    start_time: float = 0.0,
    project_width: int = 1920,
    project_height: int = 1080,
    project_fps: int = 30,
    av_generator_caps: Optional[GeneratorCapabilities] = None,
) -> Tuple[List[TimelineClip], List[TimelineClip], SceneInstance]:
    """
    Plan video and audio clips for a scene based on audio duration.

    Args:
        scene: The story scene
        audio_duration: Total audio duration for this scene (seconds)
        video_generator_caps: Capabilities of the selected video generator
        start_time: Start time on the timeline
        project_width: Project canvas width
        project_height: Project canvas height
        project_fps: Project FPS
        av_generator_caps: If set, use AV generator instead of separate video

    Returns:
        Tuple of (video_clips, audio_clips, scene_instance)
    """
    now = datetime.now().timestamp()

    # Use AV generator if available, otherwise video generator
    gen_caps = av_generator_caps or video_generator_caps
    max_clip_duration = gen_caps.max_duration_seconds

    # Determine generation mode
    is_av = av_generator_caps is not None or gen_caps.produces_audio
    gen_mode = GenerationMode.AV if is_av else GenerationMode.I2V

    # Split into N video clips
    if audio_duration <= 0:
        audio_duration = max_clip_duration  # Default to max if no audio

    n_clips = max(1, math.ceil(audio_duration / max_clip_duration))
    clip_duration = audio_duration / n_clips

    # Build the visual prompt from scene description
    visual_prompt = scene.description.visual_prompt
    negative_prompt = scene.description.negative_prompt
    motion_prompt = scene.description.motion_prompt

    # Create video clips
    video_clips: List[TimelineClip] = []
    scene_instance_id = str(uuid.uuid4())

    for i in range(n_clips):
        clip_start = start_time + (i * clip_duration)
        clip_id = str(uuid.uuid4())

        # Continuity linking
        link_from: Optional[ClipRef] = None
        if i > 0 and video_clips:
            link_from = ClipRef(
                clip_id=video_clips[i - 1].id,
                frame="last",
            )

        # Build generation spec
        gen_spec = GenerationSpec(
            mode=gen_mode,
            prompt=visual_prompt,
            negative_prompt=negative_prompt,
            motion_prompt=motion_prompt,
            camera_notes=scene.description.camera_notes,
            link_first_frame_from=link_from,
            style_ref=scene.description.style_ref,
            control_video_ref=scene.description.control_video_ref,
            character_refs=[],
            product_refs=[],
            lora_refs=[],
            audio_usage="use_generated" if is_av else None,
        )

        # Apply scene overrides
        if scene.generation_overrides.video_generator_id and not is_av:
            gen_spec.generator_id = scene.generation_overrides.video_generator_id
        elif scene.generation_overrides.av_generator_id and is_av:
            gen_spec.generator_id = scene.generation_overrides.av_generator_id
        if scene.generation_overrides.lora_refs:
            gen_spec.lora_refs = scene.generation_overrides.lora_refs
        if scene.generation_overrides.seed is not None:
            gen_spec.generator_config = {"seed": scene.generation_overrides.seed}

        video_clip = TimelineClip(
            id=clip_id,
            track_id="video_main",
            start_time=clip_start,
            duration=clip_duration,
            source_type=ClipSourceType.GENERATED_AV if is_av else ClipSourceType.GENERATED_VIDEO,
            scene_id=scene.id,
            group_id=scene_instance_id,
            generation_spec=gen_spec,
            status=ClipStatus.DRAFT,
            prompt_edited_at=now,
        )
        video_clips.append(video_clip)

    # Create audio clip(s) — one per scene, covering full duration
    audio_clips: List[TimelineClip] = []

    # Collect all script line IDs
    script_line_ids = [line.id for line in scene.script_lines]

    if script_line_ids:
        audio_clip = TimelineClip(
            id=str(uuid.uuid4()),
            track_id="audio_dialog",
            start_time=start_time,
            duration=audio_duration,
            source_type=ClipSourceType.GENERATED_AUDIO,
            scene_id=scene.id,
            group_id=scene_instance_id,
            script_line_ids=script_line_ids,
            status=ClipStatus.DRAFT,
            script_edited_at=now,
        )
        audio_clips.append(audio_clip)

    # Create scene instance
    scene_instance = SceneInstance(
        id=scene_instance_id,
        scene_id=scene.id,
        start_time=start_time,
        duration=audio_duration,
        video_clip_ids=[c.id for c in video_clips],
        audio_clip_ids=[c.id for c in audio_clips],
        locked_move=True,
    )

    return video_clips, audio_clips, scene_instance


def plan_all_scenes(
    project: VideoProject,
    registry: Optional[GeneratorRegistry] = None,
) -> Timeline:
    """
    Plan clips for all scenes in a project, building a complete timeline.

    This is a full re-plan — it replaces existing clips and scene instances.
    It preserves any manually-added clips that are not scene-linked.

    Args:
        project: The project to plan for
        registry: Generator registry (uses singleton if None)

    Returns:
        Updated Timeline
    """
    if registry is None:
        registry = get_generator_registry()

    canvas = project.settings.canvas
    defaults = project.settings.default_generators

    # Find the default video generator
    video_gen_caps = _resolve_video_generator(
        defaults.i2v or defaults.t2v,
        project.settings.vram_target_gb,
        registry,
    )

    # Find the default AV generator (if configured)
    av_gen_caps: Optional[GeneratorCapabilities] = None
    if defaults.av:
        av_gen_caps = _resolve_av_generator(
            defaults.av,
            project.settings.vram_target_gb,
            registry,
        )

    # Build new timeline preserving tracks
    timeline = project.timeline
    current_time = 0.0

    new_video_clips: List[TimelineClip] = []
    new_audio_clips: List[TimelineClip] = []
    new_scene_instances: List[SceneInstance] = []

    for scene in project.story.scenes:
        # Estimate audio duration from script lines
        audio_duration = _estimate_scene_audio_duration(scene)

        # Use scene-level generator overrides if set
        scene_video_caps = video_gen_caps
        scene_av_caps = av_gen_caps

        if scene.generation_overrides.video_generator_id:
            override_caps = _resolve_video_generator(
                scene.generation_overrides.video_generator_id,
                project.settings.vram_target_gb,
                registry,
            )
            if override_caps:
                scene_video_caps = override_caps

        if scene.generation_overrides.av_generator_id:
            override_caps = _resolve_av_generator(
                scene.generation_overrides.av_generator_id,
                project.settings.vram_target_gb,
                registry,
            )
            if override_caps:
                scene_av_caps = override_caps

        if scene_video_caps is None and scene_av_caps is None:
            # Skip scene if no generator available
            continue

        # Use a fallback caps for planning
        planning_caps = scene_video_caps or scene_av_caps
        if planning_caps is None:
            continue

        video_clips, audio_clips, instance = plan_scene_clips(
            scene=scene,
            audio_duration=audio_duration,
            video_generator_caps=planning_caps,
            start_time=current_time,
            project_width=canvas.width,
            project_height=canvas.height,
            project_fps=canvas.fps,
            av_generator_caps=scene_av_caps,
        )

        new_video_clips.extend(video_clips)
        new_audio_clips.extend(audio_clips)
        new_scene_instances.append(instance)

        current_time += instance.duration + 0.1  # Small gap between scenes

    # Preserve non-scene clips (manually imported, etc.)
    preserved_clips = [
        c for c in timeline.clips
        if c.scene_id is None and c.group_id is None
    ]

    # Assemble final timeline
    timeline.clips = preserved_clips + new_video_clips + new_audio_clips
    timeline.scene_instances = new_scene_instances
    timeline.recompute_duration()

    return timeline


# ─────────────────────────────────────────────────────────────────────────────
# Ripple operations
# ─────────────────────────────────────────────────────────────────────────────

def ripple_after(
    timeline: Timeline,
    after_time: float,
    delta: float,
    exclude_clip_ids: Optional[List[str]] = None,
) -> None:
    """
    Shift all clips starting at or after `after_time` by `delta` seconds.
    This implements ripple editing (inserting/removing time).
    """
    excluded = set(exclude_clip_ids or [])

    for clip in timeline.clips:
        if clip.id in excluded:
            continue
        if clip.start_time >= after_time:
            clip.start_time = max(0, clip.start_time + delta)

    for instance in timeline.scene_instances:
        if instance.start_time >= after_time:
            instance.start_time = max(0, instance.start_time + delta)

    timeline.recompute_duration()


def mark_scene_stale(
    timeline: Timeline,
    scene_id: str,
    stale_type: str = "prompt",
) -> int:
    """
    Mark all clips for a scene as stale.

    Args:
        timeline: The timeline to update
        scene_id: Scene to mark stale
        stale_type: What changed ("script", "prompt", "style", "keyframe")

    Returns:
        Number of clips marked stale
    """
    now = datetime.now().timestamp()
    count = 0

    for clip in timeline.clips:
        if clip.scene_id != scene_id:
            continue

        if stale_type == "script":
            clip.script_edited_at = now
        elif stale_type == "prompt":
            clip.prompt_edited_at = now
        elif stale_type == "style":
            clip.style_edited_at = now
        elif stale_type == "keyframe":
            clip.keyframe_edited_at = now

        if clip.status == ClipStatus.DONE:
            clip.status = ClipStatus.STALE
        count += 1

    return count


def get_stale_clips(timeline: Timeline) -> List[TimelineClip]:
    """Get all clips that need regeneration."""
    stale: List[TimelineClip] = []
    for clip in timeline.clips:
        if clip.status == ClipStatus.STALE:
            stale.append(clip)
        elif clip.is_video_stale or clip.is_audio_stale:
            stale.append(clip)
    return stale


# ─────────────────────────────────────────────────────────────────────────────
# Re-planning (when generator changes)
# ─────────────────────────────────────────────────────────────────────────────

def replan_scene(
    project: VideoProject,
    scene_id: str,
    new_generator_id: Optional[str] = None,
    registry: Optional[GeneratorRegistry] = None,
) -> Optional[SceneInstance]:
    """
    Re-plan a single scene's clips (e.g. when generator or audio changes).
    Preserves the scene's start time but recalculates clip splits.

    Returns the new SceneInstance, or None if the scene is not found.
    """
    if registry is None:
        registry = get_generator_registry()

    # Find scene
    scene = next((s for s in project.story.scenes if s.id == scene_id), None)
    if not scene:
        return None

    # Find existing instance
    old_instance = next(
        (si for si in project.timeline.scene_instances if si.scene_id == scene_id),
        None,
    )
    start_time = old_instance.start_time if old_instance else 0.0

    # Remove old clips for this scene
    old_clip_ids = set()
    if old_instance:
        old_clip_ids = set(old_instance.video_clip_ids + old_instance.audio_clip_ids)

    project.timeline.clips = [
        c for c in project.timeline.clips if c.id not in old_clip_ids
    ]
    project.timeline.scene_instances = [
        si for si in project.timeline.scene_instances if si.scene_id != scene_id
    ]

    # Resolve generator
    gen_id = new_generator_id or scene.generation_overrides.video_generator_id
    video_caps = _resolve_video_generator(
        gen_id or project.settings.default_generators.i2v or project.settings.default_generators.t2v,
        project.settings.vram_target_gb,
        registry,
    )

    av_caps: Optional[GeneratorCapabilities] = None
    av_id = scene.generation_overrides.av_generator_id or project.settings.default_generators.av
    if av_id:
        av_caps = _resolve_av_generator(av_id, project.settings.vram_target_gb, registry)

    if video_caps is None and av_caps is None:
        return None

    planning_caps = video_caps or av_caps
    if planning_caps is None:
        return None

    audio_duration = _estimate_scene_audio_duration(scene)

    video_clips, audio_clips, instance = plan_scene_clips(
        scene=scene,
        audio_duration=audio_duration,
        video_generator_caps=planning_caps,
        start_time=start_time,
        project_width=project.settings.canvas.width,
        project_height=project.settings.canvas.height,
        project_fps=project.settings.canvas.fps,
        av_generator_caps=av_caps,
    )

    project.timeline.clips.extend(video_clips)
    project.timeline.clips.extend(audio_clips)
    project.timeline.scene_instances.append(instance)
    project.timeline.recompute_duration()

    return instance


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _estimate_scene_audio_duration(scene: StoryScene) -> float:
    """
    Estimate total audio duration for a scene from script lines.
    Uses duration hints if available, otherwise estimates from text length.
    """
    total = 0.0

    for line in scene.script_lines:
        if line.duration_hint and line.duration_hint > 0:
            total += line.duration_hint
        else:
            # Rough estimate: ~150 words per minute, ~5 chars per word
            word_count = len(line.text.split())
            total += max(1.0, word_count / 2.5)  # ~2.5 words/sec

    return max(1.0, total)  # At least 1 second


def _resolve_video_generator(
    generator_id: Optional[str],
    vram_available: float,
    registry: GeneratorRegistry,
) -> Optional[GeneratorCapabilities]:
    """Resolve a video generator by ID or find a compatible one."""
    if generator_id:
        gen_class = registry.get_generator_class(generator_id)
        if gen_class:
            return gen_class.get_capabilities()

    # Fall back to any compatible video generator
    compatible = registry.find_compatible(
        generator_type=GeneratorType.I2V,
        vram_available_gb=vram_available,
    )
    if not compatible:
        compatible = registry.find_compatible(
            generator_type=GeneratorType.T2V,
            vram_available_gb=vram_available,
        )

    return compatible[0] if compatible else None


def _resolve_av_generator(
    generator_id: Optional[str],
    vram_available: float,
    registry: GeneratorRegistry,
) -> Optional[GeneratorCapabilities]:
    """Resolve an AV generator by ID or find a compatible one."""
    if generator_id:
        gen_class = registry.get_generator_class(generator_id)
        if gen_class:
            caps = gen_class.get_capabilities()
            if caps.produces_audio and caps.produces_video:
                return caps

    # Fall back to any compatible AV generator
    compatible = registry.find_compatible(
        generator_type=GeneratorType.AV,
        vram_available_gb=vram_available,
        requires_audio_output=True,
    )
    return compatible[0] if compatible else None


# ─────────────────────────────────────────────────────────────────────────────
# RPC Handler
# ─────────────────────────────────────────────────────────────────────────────

async def handle_ve_plan_scene(payload: Dict) -> Dict:
    """RPC handler for planning/re-planning a scene."""
    from apps.video_editor.project import get_open_project

    project_id = payload.get("projectId", "")
    scene_id = payload.get("sceneId", "")
    generator_id = payload.get("generatorId")

    project = get_open_project(project_id)
    if not project:
        return {"success": False, "error": "Project not found or not open"}

    if not scene_id:
        return {"success": False, "error": "Scene ID is required"}

    instance = replan_scene(project, scene_id, generator_id)
    if not instance:
        return {"success": False, "error": "Failed to plan scene (no generator or scene not found)"}

    return {
        "success": True,
        "scene_instance": instance.model_dump(),
        "timeline": project.timeline.model_dump(),
    }


async def handle_ve_plan_all_scenes(payload: Dict) -> Dict:
    """RPC handler for planning all scenes."""
    from apps.video_editor.project import get_open_project

    project_id = payload.get("projectId", "")
    project = get_open_project(project_id)
    if not project:
        return {"success": False, "error": "Project not found or not open"}

    timeline = plan_all_scenes(project)
    return {
        "success": True,
        "timeline": timeline.model_dump(),
    }
