"""
Video Editor Pydantic Models - Single Source of Truth

This module defines all data models for the video editor, including:
- Project settings and state
- Asset library (characters, props, voices)
- Story and scenes
- Timeline and clips
- Jobs and generation state
- Generator capabilities
"""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any, Tuple
from pydantic import BaseModel, Field
import uuid


# ─────────────────────────────────────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────────────────────────────────────

class Orientation(str, Enum):
    LANDSCAPE = "landscape"
    PORTRAIT = "portrait"
    SQUARE = "square"


class ClipSourceType(str, Enum):
    GENERATED_VIDEO = "generated_video"
    GENERATED_IMAGE = "generated_image"
    IMPORTED = "imported"
    PLACEHOLDER = "placeholder"
    AUDIO = "audio"


class ClipStatus(str, Enum):
    DRAFT = "draft"
    KEYFRAME_READY = "keyframe_ready"
    QUEUED = "queued"
    GENERATING = "generating"
    DONE = "done"
    ERROR = "error"


class GenerationMode(str, Enum):
    PROMPT_ONLY = "prompt_only"
    I2V = "i2v"  # Image to Video
    FLF = "flf"  # First + Last Frame interpolation
    T2V = "t2v"  # Text to Video


class JobStatus(str, Enum):
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobType(str, Enum):
    STORY_GENERATE = "story_generate"
    TTS_GENERATE = "tts_generate"
    IMAGE_GENERATE = "image_generate"
    VIDEO_GENERATE = "video_generate"
    MUSIC_GENERATE = "music_generate"
    FINAL_MERGE = "final_merge"


class RegenerationMode(str, Enum):
    PREVIEW_AUDIO = "preview_audio"
    REGEN_AUDIO = "regen_audio"
    REGEN_VIDEO = "regen_video"
    REGEN_AUDIO_VIDEO = "regen_audio_video"
    REGEN_CHAIN = "regen_chain"
    REGEN_ALL_STALE = "regen_all_stale"


# ─────────────────────────────────────────────────────────────────────────────
# Canvas / Project Settings
# ─────────────────────────────────────────────────────────────────────────────

class CanvasPreset(BaseModel):
    """Predefined canvas size preset."""
    name: str
    width: int
    height: int
    fps: int = 30
    orientation: Orientation


# Common presets
CANVAS_PRESETS: Dict[str, CanvasPreset] = {
    "1080p_landscape": CanvasPreset(name="1080p Landscape", width=1920, height=1080, fps=30, orientation=Orientation.LANDSCAPE),
    "1080p_portrait": CanvasPreset(name="1080p Portrait", width=1080, height=1920, fps=30, orientation=Orientation.PORTRAIT),
    "720p_landscape": CanvasPreset(name="720p Landscape", width=1280, height=720, fps=30, orientation=Orientation.LANDSCAPE),
    "720p_portrait": CanvasPreset(name="720p Portrait", width=720, height=1280, fps=30, orientation=Orientation.PORTRAIT),
    "4k_landscape": CanvasPreset(name="4K Landscape", width=3840, height=2160, fps=30, orientation=Orientation.LANDSCAPE),
    "square_1080": CanvasPreset(name="Square 1080", width=1080, height=1080, fps=30, orientation=Orientation.SQUARE),
    "youtube_shorts": CanvasPreset(name="YouTube Shorts", width=1080, height=1920, fps=30, orientation=Orientation.PORTRAIT),
    "tiktok": CanvasPreset(name="TikTok", width=1080, height=1920, fps=30, orientation=Orientation.PORTRAIT),
    "instagram_reel": CanvasPreset(name="Instagram Reel", width=1080, height=1920, fps=30, orientation=Orientation.PORTRAIT),
}


class CanvasSettings(BaseModel):
    """Canvas/video settings for the project."""
    preset: Optional[str] = None  # Key from CANVAS_PRESETS or None for custom
    width: int = 1920
    height: int = 1080
    fps: int = 30
    orientation: Orientation = Orientation.LANDSCAPE


class DefaultGeneratorSelections(BaseModel):
    """Default model/generator selections for the project."""
    story_llm: Optional[str] = None  # Generator ID for story generation
    tts: Optional[str] = None  # Generator ID for TTS
    t2i: Optional[str] = None  # Generator ID for text-to-image
    i2v: Optional[str] = None  # Generator ID for image-to-video
    t2v: Optional[str] = None  # Generator ID for text-to-video
    music: Optional[str] = None  # Generator ID for music/SFX
    upscaler: Optional[str] = None  # Generator ID for upscaling


class ProjectSettings(BaseModel):
    """Project-level settings."""
    vram_target_gb: float = 24.0  # Target VRAM in GB (e.g., 24 for RTX 4090)
    canvas: CanvasSettings = Field(default_factory=CanvasSettings)
    default_generators: DefaultGeneratorSelections = Field(default_factory=DefaultGeneratorSelections)


# ─────────────────────────────────────────────────────────────────────────────
# Asset Library
# ─────────────────────────────────────────────────────────────────────────────

class AssetRef(BaseModel):
    """Reference to an asset by ID."""
    asset_id: str
    asset_type: str  # "character", "prop", "voice", "image", "video", "audio"


class CharacterAsset(BaseModel):
    """Character definition in the asset library."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    code: str  # Short code for referencing in scripts
    description: Optional[str] = None
    image_path: Optional[str] = None  # Relative path within project
    voice_sample_path: Optional[str] = None  # Voice sample for TTS cloning
    lora_path: Optional[str] = None  # Optional LoRA for this character
    style_hints: Optional[str] = None  # Style description for generation
    created_at: float = Field(default_factory=lambda: datetime.now().timestamp())
    updated_at: float = Field(default_factory=lambda: datetime.now().timestamp())


class PropAsset(BaseModel):
    """Prop/background asset in the library."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    code: str  # Short code for referencing
    description: Optional[str] = None
    image_path: Optional[str] = None
    category: Optional[str] = None  # "background", "object", "effect", etc.
    created_at: float = Field(default_factory=lambda: datetime.now().timestamp())
    updated_at: float = Field(default_factory=lambda: datetime.now().timestamp())


class VoiceAsset(BaseModel):
    """Voice profile for TTS."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    code: str
    sample_path: str  # Path to voice sample
    description: Optional[str] = None
    language: str = "en"
    gender: Optional[str] = None  # "male", "female", "neutral"
    created_at: float = Field(default_factory=lambda: datetime.now().timestamp())
    updated_at: float = Field(default_factory=lambda: datetime.now().timestamp())


class GeneratedAsset(BaseModel):
    """A generated image/video/audio asset."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    asset_type: str  # "image", "video", "audio"
    path: str  # Relative path within project
    source_prompt: Optional[str] = None
    generator_id: Optional[str] = None
    generator_config: Optional[Dict[str, Any]] = None
    width: Optional[int] = None
    height: Optional[int] = None
    duration_seconds: Optional[float] = None
    created_at: float = Field(default_factory=lambda: datetime.now().timestamp())


class AssetLibrary(BaseModel):
    """Complete asset library for a project."""
    characters: List[CharacterAsset] = Field(default_factory=list)
    props: List[PropAsset] = Field(default_factory=list)
    voices: List[VoiceAsset] = Field(default_factory=list)
    generated: List[GeneratedAsset] = Field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# Story / Script
# ─────────────────────────────────────────────────────────────────────────────

class ScriptLine(BaseModel):
    """A single line of dialog/narration in a script."""
    character_id: Optional[str] = None  # None = narrator
    text: str
    emotion_hint: Optional[str] = None  # "happy", "angry", "whisper", etc.
    voice_override: Optional[str] = None  # Override voice for this line
    duration_hint: Optional[float] = None  # Suggested duration in seconds


class ClipScript(BaseModel):
    """Script content for a single clip."""
    lines: List[ScriptLine] = Field(default_factory=list)


class SceneDescription(BaseModel):
    """Visual description of a scene."""
    visual_prompt: str  # Prompt for image/video generation
    negative_prompt: Optional[str] = None
    motion_prompt: Optional[str] = None  # For video, describes motion
    camera_notes: Optional[str] = None  # Camera angle, movement
    style_ref: Optional[AssetRef] = None  # Style reference image


class StoryScene(BaseModel):
    """A scene in the story."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: Optional[str] = None
    order: int = 0
    script: ClipScript = Field(default_factory=ClipScript)
    description: SceneDescription = Field(default_factory=lambda: SceneDescription(visual_prompt=""))
    character_ids: List[str] = Field(default_factory=list)  # Characters in this scene
    prop_ids: List[str] = Field(default_factory=list)  # Props/backgrounds
    duration_estimate: Optional[float] = None  # Estimated duration in seconds
    notes: Optional[str] = None


class Story(BaseModel):
    """The complete story structure."""
    title: Optional[str] = None
    genre: Optional[str] = None  # "advertising", "movie", "documentary", etc.
    synopsis: Optional[str] = None
    scenes: List[StoryScene] = Field(default_factory=list)
    created_at: float = Field(default_factory=lambda: datetime.now().timestamp())
    updated_at: float = Field(default_factory=lambda: datetime.now().timestamp())


# ─────────────────────────────────────────────────────────────────────────────
# Timeline / Clips
# ─────────────────────────────────────────────────────────────────────────────

class ClipRef(BaseModel):
    """Reference to another clip (for linking/continuity)."""
    clip_id: str
    frame: str = "last"  # "first", "last", or frame number


class GenerationSpec(BaseModel):
    """Specification for generating content for a clip."""
    mode: GenerationMode = GenerationMode.PROMPT_ONLY
    prompt: Optional[str] = None
    negative_prompt: Optional[str] = None
    motion_prompt: Optional[str] = None
    
    # Keyframe references
    first_frame: Optional[AssetRef] = None  # For I2V start or FLF start
    last_frame: Optional[AssetRef] = None  # For FLF end
    
    # Continuity linking (resolved at job time)
    link_first_frame_from: Optional[ClipRef] = None  # "use last frame of clip X"
    link_last_frame_to: Optional[ClipRef] = None  # "my last frame feeds clip Y"
    
    # Style/character injection
    style_ref: Optional[AssetRef] = None
    character_refs: List[AssetRef] = Field(default_factory=list)  # For IP-adapter
    
    # Model override
    generator_id: Optional[str] = None
    generator_config: Optional[Dict[str, Any]] = None


class TimelineClip(BaseModel):
    """A clip on the timeline."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    track_id: str = "main"  # For multi-track support
    start_time: float = 0.0  # Start time in seconds
    duration: float = 0.0  # Duration in seconds
    
    # Content source
    source_type: ClipSourceType = ClipSourceType.PLACEHOLDER
    scene_id: Optional[str] = None  # Link to story scene
    
    # Generation spec (for video/image clips)
    generation_spec: Optional[GenerationSpec] = None
    
    # Script content (for incremental regeneration)
    script: Optional[ClipScript] = None
    
    # State
    status: ClipStatus = ClipStatus.DRAFT
    keyframe_path: Optional[str] = None  # Generated/uploaded keyframe image
    artifact_path: Optional[str] = None  # Final video/audio artifact
    preview_path: Optional[str] = None  # Low-res preview
    
    # Staleness tracking for incremental regeneration
    script_edited_at: Optional[float] = None
    keyframe_edited_at: Optional[float] = None
    style_edited_at: Optional[float] = None
    audio_generated_at: Optional[float] = None
    video_generated_at: Optional[float] = None
    
    # Computed properties
    @property
    def is_audio_stale(self) -> bool:
        if self.audio_generated_at is None:
            return True
        return (self.script_edited_at or 0) > self.audio_generated_at
    
    @property
    def is_video_stale(self) -> bool:
        if self.video_generated_at is None:
            return True
        if self.is_audio_stale:
            return True  # Audio changes cascade to video
        return max(self.keyframe_edited_at or 0, self.style_edited_at or 0) > self.video_generated_at


class TimelineTrack(BaseModel):
    """A track on the timeline (for multi-track editing)."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str = "Main"
    type: str = "video"  # "video", "audio", "overlay"
    order: int = 0
    muted: bool = False
    locked: bool = False


class Timeline(BaseModel):
    """The complete timeline."""
    tracks: List[TimelineTrack] = Field(default_factory=lambda: [TimelineTrack(id="main", name="Main", type="video")])
    clips: List[TimelineClip] = Field(default_factory=list)
    total_duration: float = 0.0  # Computed from clips
    
    def recompute_duration(self) -> None:
        """Recompute total duration from clips."""
        if not self.clips:
            self.total_duration = 0.0
        else:
            self.total_duration = max(
                clip.start_time + clip.duration for clip in self.clips
            )


# ─────────────────────────────────────────────────────────────────────────────
# Jobs
# ─────────────────────────────────────────────────────────────────────────────

class JobProgressEvent(BaseModel):
    """Progress event for a running job."""
    job_id: str
    seq: int  # Sequence number for resumption
    stage: str  # 'extracting_frame', 'generating_keyframe', 'generating_video', etc.
    stage_progress: float = 0.0  # 0.0 - 1.0
    overall_progress: float = 0.0  # 0.0 - 1.0
    current_frame: Optional[int] = None
    total_frames: Optional[int] = None
    preview_url: Optional[str] = None  # Progressive preview
    eta_seconds: Optional[float] = None
    message: Optional[str] = None


class Job(BaseModel):
    """A generation job."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: JobType
    status: JobStatus = JobStatus.PENDING
    
    # What this job operates on
    clip_ids: List[str] = Field(default_factory=list)
    scene_ids: List[str] = Field(default_factory=list)
    
    # Dependencies (jobs that must complete before this one)
    depends_on: List[str] = Field(default_factory=list)
    
    # Generator to use
    generator_id: Optional[str] = None
    generator_config: Optional[Dict[str, Any]] = None
    
    # VRAM requirement (for queue scheduling)
    vram_gb_required: float = 0.0
    
    # Timing
    created_at: float = Field(default_factory=lambda: datetime.now().timestamp())
    started_at: Optional[float] = None
    completed_at: Optional[float] = None
    
    # Results
    artifact_paths: List[str] = Field(default_factory=list)
    error_message: Optional[str] = None
    
    # Progress tracking
    last_seq: int = 0
    last_progress: float = 0.0


class JobQueue(BaseModel):
    """Queue of jobs for a project."""
    jobs: List[Job] = Field(default_factory=list)
    active_job_id: Optional[str] = None
    vram_in_use_gb: float = 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Project State (Complete)
# ─────────────────────────────────────────────────────────────────────────────

class VideoProject(BaseModel):
    """Complete video project state."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    version: str = "1.0.0"  # Schema version for migrations
    
    # Settings
    settings: ProjectSettings = Field(default_factory=ProjectSettings)
    
    # Content
    library: AssetLibrary = Field(default_factory=AssetLibrary)
    story: Story = Field(default_factory=Story)
    timeline: Timeline = Field(default_factory=Timeline)
    
    # Jobs
    job_queue: JobQueue = Field(default_factory=JobQueue)
    
    # Metadata
    created_at: float = Field(default_factory=lambda: datetime.now().timestamp())
    updated_at: float = Field(default_factory=lambda: datetime.now().timestamp())
    
    # Paths (set when project is opened)
    root_path: Optional[str] = None  # User-selected folder
    
    def update_timestamp(self) -> None:
        """Update the updated_at timestamp."""
        self.updated_at = datetime.now().timestamp()


# ─────────────────────────────────────────────────────────────────────────────
# Generator Capabilities (for plugin system)
# ─────────────────────────────────────────────────────────────────────────────

class GeneratorCapabilities(BaseModel):
    """Capabilities declared by a generator plugin."""
    # Identity
    id: str
    title: str
    description: Optional[str] = None
    version: str = "1.0.0"
    
    # Generator type
    generator_type: str  # "llm", "tts", "t2i", "i2v", "t2v", "music", "upscaler"
    
    # Resource requirements
    vram_gb_min: float = 0.0
    vram_gb_recommended: float = 0.0
    ram_gb_min: float = 0.0
    
    # Format support
    supported_formats: List[str] = Field(default_factory=list)  # ["Portrait", "Landscape", "Square"]
    
    # Advanced capabilities
    supports_ip_adapter: bool = False
    supports_lora: bool = False
    max_subjects: int = 1
    accepts_text_prompt: bool = True
    accepts_negative_prompt: bool = False
    
    # Video-specific
    supports_i2v: bool = False  # Image-to-video
    supports_t2v: bool = False  # Text-to-video
    supports_flf: bool = False  # First+last frame interpolation
    supports_preview_mode: bool = False  # Fast low-quality generation
    supports_camera_control: bool = False
    supported_control_nets: List[str] = Field(default_factory=list)  # ["depth", "pose", "canny"]
    
    # Resolution constraints
    valid_resolutions: List[Tuple[int, int]] = Field(default_factory=list)
    resolution_must_be_divisible_by: int = 8
    max_frames: int = 120
    max_duration_seconds: float = 5.0
    
    # TTS-specific
    supports_voice_cloning: bool = False
    supported_languages: List[str] = Field(default_factory=lambda: ["en"])
    
    # LLM-specific (for story generator)
    max_context_tokens: int = 0
    supports_streaming: bool = False


class GeneratorConfig(BaseModel):
    """User-configurable settings for a generator instance."""
    generator_id: str
    model_path: Optional[str] = None  # Local model path
    api_key: Optional[str] = None  # For API-based generators
    api_base_url: Optional[str] = None
    
    # Common settings
    seed: Optional[int] = None
    steps: Optional[int] = None
    cfg_scale: Optional[float] = None
    
    # Generator-specific settings (flexible dict)
    custom: Dict[str, Any] = Field(default_factory=dict)


# ─────────────────────────────────────────────────────────────────────────────
# RPC Request/Response Types
# ─────────────────────────────────────────────────────────────────────────────

class CreateProjectRequest(BaseModel):
    """Request to create a new video project."""
    folder_path: str  # User-selected folder
    name: str
    settings: Optional[ProjectSettings] = None


class CreateProjectResponse(BaseModel):
    """Response from creating a project."""
    success: bool
    project: Optional[VideoProject] = None
    error: Optional[str] = None


class OpenProjectRequest(BaseModel):
    """Request to open an existing project."""
    folder_path: str  # Folder containing xeditor.video.project.json


class OpenProjectResponse(BaseModel):
    """Response from opening a project."""
    success: bool
    project: Optional[VideoProject] = None
    error: Optional[str] = None


class SaveProjectRequest(BaseModel):
    """Request to save project state."""
    project_id: str


class SaveProjectResponse(BaseModel):
    """Response from saving a project."""
    success: bool
    error: Optional[str] = None


class StartJobRequest(BaseModel):
    """Request to start a generation job."""
    project_id: str
    job_type: JobType
    clip_ids: List[str] = Field(default_factory=list)
    scene_ids: List[str] = Field(default_factory=list)
    generator_id: Optional[str] = None
    generator_config: Optional[Dict[str, Any]] = None
    regeneration_mode: Optional[RegenerationMode] = None


class StartJobResponse(BaseModel):
    """Response from starting a job."""
    success: bool
    job_id: Optional[str] = None
    error: Optional[str] = None


class CancelJobRequest(BaseModel):
    """Request to cancel a running job."""
    project_id: str
    job_id: str


class CancelJobResponse(BaseModel):
    """Response from cancelling a job."""
    success: bool
    error: Optional[str] = None
