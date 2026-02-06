"""
Base Generator Classes and Registry (v2)

Defines the abstract base classes for all generator types,
result types, and the registry for discovering/managing generators.

Generator types:
- LLM: Story/script generation
- TTS: Text-to-speech
- ImageGenerator: Text-to-image
- VideoGenerator: Image-to-video / Text-to-video
- AudioVideoGenerator: Joint audio+video (e.g. LTX-2)
- MusicGenerator: Music/background audio
- SFXGenerator: Sound effects
- LipSyncGenerator: Audio-driven lip sync
- UpscalerGenerator: Image/video upscaling
"""

import abc
import asyncio
from dataclasses import dataclass, field as dc_field
from datetime import datetime
from pathlib import Path
from typing import (
    Any,
    AsyncGenerator,
    Callable,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
    Type,
    TypeVar,
)

from apps.video_editor.models import (
    GeneratorCapabilities,
    GeneratorConfig,
    GeneratorType,
    JobProgressEvent,
    AssetRef,
    ShapeConstraints,
    FrameCountRule,
)


# ─────────────────────────────────────────────────────────────────────────────
# Progress callback type
# ─────────────────────────────────────────────────────────────────────────────

ProgressCallback = Callable[[JobProgressEvent], Any]


# ─────────────────────────────────────────────────────────────────────────────
# Result types
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class GenerationResult:
    """Base result from any generation operation."""
    success: bool
    artifact_path: Optional[str] = None
    artifact_paths: Optional[List[str]] = None
    duration_seconds: Optional[float] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


@dataclass
class LLMResult:
    """Result from LLM generation."""
    success: bool
    content: str = ""
    finish_reason: Optional[str] = None
    usage: Optional[Dict[str, int]] = None
    error: Optional[str] = None


@dataclass
class TTSResult(GenerationResult):
    """Result from TTS generation."""
    text: str = ""
    duration_seconds: float = 0.0
    sample_rate: int = 22050


@dataclass
class ImageResult(GenerationResult):
    """Result from image generation."""
    width: int = 0
    height: int = 0
    seed: Optional[int] = None


@dataclass
class VideoResult(GenerationResult):
    """Result from video generation."""
    width: int = 0
    height: int = 0
    fps: float = 30.0
    frame_count: int = 0
    duration_seconds: float = 0.0
    seed: Optional[int] = None


@dataclass
class AudioVideoResult(GenerationResult):
    """
    Result from joint audio+video generation (e.g. LTX-2).
    Returns both a video and an audio artifact.
    """
    video_artifact_path: Optional[str] = None
    audio_artifact_path: Optional[str] = None
    width: int = 0
    height: int = 0
    fps: float = 30.0
    frame_count: int = 0
    duration_seconds: float = 0.0
    sample_rate: int = 44100
    seed: Optional[int] = None


@dataclass
class LipSyncResult(GenerationResult):
    """Result from lip-sync generation."""
    width: int = 0
    height: int = 0
    fps: float = 30.0
    frame_count: int = 0
    duration_seconds: float = 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Shape constraint validation helpers
# ─────────────────────────────────────────────────────────────────────────────

def validate_shape(
    width: int,
    height: int,
    num_frames: Optional[int],
    fps: Optional[int],
    constraints: ShapeConstraints,
) -> List[str]:
    """
    Validate resolution/frames/fps against generator shape constraints.
    Returns a list of error messages (empty = valid).
    """
    errors: List[str] = []

    if width % constraints.width_divisible_by != 0:
        errors.append(
            f"Width {width} must be divisible by {constraints.width_divisible_by}"
        )
    if height % constraints.height_divisible_by != 0:
        errors.append(
            f"Height {height} must be divisible by {constraints.height_divisible_by}"
        )

    if constraints.min_width and width < constraints.min_width:
        errors.append(f"Width {width} is below minimum {constraints.min_width}")
    if constraints.max_width and width > constraints.max_width:
        errors.append(f"Width {width} exceeds maximum {constraints.max_width}")
    if constraints.min_height and height < constraints.min_height:
        errors.append(f"Height {height} is below minimum {constraints.min_height}")
    if constraints.max_height and height > constraints.max_height:
        errors.append(f"Height {height} exceeds maximum {constraints.max_height}")

    if num_frames is not None and constraints.frame_count_rule:
        rule = constraints.frame_count_rule
        if (num_frames - rule.offset) % rule.divisor != 0:
            errors.append(
                f"Frame count {num_frames} must satisfy "
                f"(n - {rule.offset}) % {rule.divisor} == 0"
            )
        if rule.min_frames and num_frames < rule.min_frames:
            errors.append(
                f"Frame count {num_frames} is below minimum {rule.min_frames}"
            )
        if rule.max_frames and num_frames > rule.max_frames:
            errors.append(
                f"Frame count {num_frames} exceeds maximum {rule.max_frames}"
            )

    if fps is not None:
        if constraints.supported_fps and fps not in constraints.supported_fps:
            errors.append(
                f"FPS {fps} not in supported values {constraints.supported_fps}"
            )
        if constraints.min_fps and fps < constraints.min_fps:
            errors.append(f"FPS {fps} is below minimum {constraints.min_fps}")
        if constraints.max_fps and fps > constraints.max_fps:
            errors.append(f"FPS {fps} exceeds maximum {constraints.max_fps}")

    return errors


# ─────────────────────────────────────────────────────────────────────────────
# Base Generator Class
# ─────────────────────────────────────────────────────────────────────────────

class BaseGenerator(abc.ABC):
    """
    Abstract base class for all generators.

    Generators are services that:
    1. Declare their capabilities (including UI schema + shape constraints)
    2. Receive inputs and produce typed outputs
    3. Manage VRAM lifecycle (load/unload)
    4. Report progress via callbacks
    """

    def __init__(self, config: Optional[GeneratorConfig] = None):
        self.config = config or GeneratorConfig(generator_id=self.get_id())
        self._loaded = False

    @classmethod
    @abc.abstractmethod
    def get_id(cls) -> str:
        """Unique identifier for this generator."""
        ...

    @classmethod
    @abc.abstractmethod
    def get_capabilities(cls) -> GeneratorCapabilities:
        """Capabilities, UI schema, and shape constraints."""
        ...

    @abc.abstractmethod
    async def load(self) -> None:
        """Load model into VRAM/memory. Must be idempotent."""
        ...

    @abc.abstractmethod
    async def unload(self) -> None:
        """Unload model from VRAM/memory. Clear GPU memory aggressively."""
        ...

    def is_loaded(self) -> bool:
        return self._loaded

    async def __aenter__(self) -> "BaseGenerator":
        await self.load()
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        await self.unload()

    def validate_config(self) -> List[str]:
        """Validate current configuration. Returns error messages (empty = valid)."""
        return []


# ─────────────────────────────────────────────────────────────────────────────
# Specialized Generator Base Classes
# ─────────────────────────────────────────────────────────────────────────────

class LLMGenerator(BaseGenerator):
    """Base class for LLM generators (story generation, etc.)."""

    @abc.abstractmethod
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> LLMResult:
        ...

    async def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> AsyncGenerator[str, None]:
        result = await self.generate(prompt, system_prompt, max_tokens, temperature)
        if result.success:
            yield result.content


class TTSGenerator(BaseGenerator):
    """Base class for TTS generators."""

    @abc.abstractmethod
    async def generate(
        self,
        text: str,
        output_path: str,
        voice_sample_path: Optional[str] = None,
        language: str = "en",
        speed: float = 1.0,
        emotion: Optional[str] = None,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> TTSResult:
        ...


class ImageGenerator(BaseGenerator):
    """Base class for image generators (T2I)."""

    @abc.abstractmethod
    async def generate(
        self,
        prompt: str,
        output_path: str,
        negative_prompt: Optional[str] = None,
        width: int = 1024,
        height: int = 1024,
        seed: Optional[int] = None,
        steps: Optional[int] = None,
        cfg_scale: Optional[float] = None,
        style_ref: Optional[str] = None,
        character_refs: Optional[List[str]] = None,
        product_refs: Optional[List[str]] = None,
        lora_paths: Optional[List[str]] = None,
        control_image: Optional[str] = None,
        control_type: Optional[str] = None,
        preview_mode: bool = False,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> ImageResult:
        ...


class VideoGenerator(BaseGenerator):
    """Base class for video generators (I2V, T2V, FLF)."""

    @abc.abstractmethod
    async def generate(
        self,
        output_path: str,
        prompt: Optional[str] = None,
        negative_prompt: Optional[str] = None,
        motion_prompt: Optional[str] = None,
        first_frame_path: Optional[str] = None,
        last_frame_path: Optional[str] = None,
        duration_seconds: float = 4.0,
        fps: int = 30,
        width: int = 1024,
        height: int = 576,
        seed: Optional[int] = None,
        steps: Optional[int] = None,
        cfg_scale: Optional[float] = None,
        style_ref: Optional[str] = None,
        character_refs: Optional[List[str]] = None,
        product_refs: Optional[List[str]] = None,
        lora_paths: Optional[List[str]] = None,
        control_video: Optional[str] = None,
        control_type: Optional[str] = None,
        camera_motion: Optional[str] = None,
        preview_mode: bool = False,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> VideoResult:
        ...


class AudioVideoGenerator(BaseGenerator):
    """
    Base class for joint audio+video generators (e.g. LTX-2).

    These produce both a video file and a synchronized audio file
    in a single generation pass.
    """

    @abc.abstractmethod
    async def generate(
        self,
        video_output_path: str,
        audio_output_path: str,
        prompt: Optional[str] = None,
        negative_prompt: Optional[str] = None,
        motion_prompt: Optional[str] = None,
        first_frame_path: Optional[str] = None,
        last_frame_path: Optional[str] = None,
        audio_prompt: Optional[str] = None,
        audio_input_path: Optional[str] = None,
        duration_seconds: float = 4.0,
        fps: int = 24,
        width: int = 1024,
        height: int = 576,
        seed: Optional[int] = None,
        steps: Optional[int] = None,
        cfg_scale: Optional[float] = None,
        style_ref: Optional[str] = None,
        character_refs: Optional[List[str]] = None,
        product_refs: Optional[List[str]] = None,
        lora_paths: Optional[List[str]] = None,
        control_video: Optional[str] = None,
        control_type: Optional[str] = None,
        camera_motion: Optional[str] = None,
        preview_mode: bool = False,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> AudioVideoResult:
        ...


class MusicGenerator(BaseGenerator):
    """Base class for music generators."""

    @abc.abstractmethod
    async def generate(
        self,
        prompt: str,
        output_path: str,
        duration_seconds: float = 30.0,
        lyrics: Optional[str] = None,
        style: Optional[str] = None,
        seed: Optional[int] = None,
        temperature: float = 1.0,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> GenerationResult:
        ...


class SFXGenerator(BaseGenerator):
    """Base class for sound effect generators."""

    @abc.abstractmethod
    async def generate(
        self,
        prompt: str,
        output_path: str,
        duration_seconds: float = 5.0,
        seed: Optional[int] = None,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> GenerationResult:
        ...


class LipSyncGenerator(BaseGenerator):
    """Base class for audio-driven lip sync generators."""

    @abc.abstractmethod
    async def generate(
        self,
        video_input_path: str,
        audio_input_path: str,
        output_path: str,
        face_ref_path: Optional[str] = None,
        mask_roi: Optional[Tuple[int, int, int, int]] = None,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> LipSyncResult:
        ...


class UpscalerGenerator(BaseGenerator):
    """Base class for upscaling/enhancement generators."""

    @abc.abstractmethod
    async def upscale(
        self,
        input_path: str,
        output_path: str,
        scale_factor: float = 2.0,
        denoise: bool = False,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> GenerationResult:
        ...


# ─────────────────────────────────────────────────────────────────────────────
# Generator Registry
# ─────────────────────────────────────────────────────────────────────────────

T = TypeVar("T", bound=BaseGenerator)

# Map generator type to expected base class
GENERATOR_TYPE_BASE_MAP: Dict[GeneratorType, Type[BaseGenerator]] = {
    GeneratorType.LLM: LLMGenerator,
    GeneratorType.TTS: TTSGenerator,
    GeneratorType.T2I: ImageGenerator,
    GeneratorType.I2V: VideoGenerator,
    GeneratorType.T2V: VideoGenerator,
    GeneratorType.AV: AudioVideoGenerator,
    GeneratorType.MUSIC: MusicGenerator,
    GeneratorType.SFX: SFXGenerator,
    GeneratorType.LIPSYNC: LipSyncGenerator,
    GeneratorType.UPSCALER: UpscalerGenerator,
}


class GeneratorRegistry:
    """
    Registry for discovering and managing generator plugins.

    Generators can be registered programmatically or discovered
    from a plugins directory.
    """

    def __init__(self) -> None:
        self._generators: Dict[str, Type[BaseGenerator]] = {}
        self._instances: Dict[str, BaseGenerator] = {}
        self._builtin_ids: Set[str] = set()

    def register(
        self,
        generator_class: Type[BaseGenerator],
        is_builtin: bool = True,
    ) -> None:
        """Register a generator class."""
        generator_id = generator_class.get_id()
        self._generators[generator_id] = generator_class
        if is_builtin:
            self._builtin_ids.add(generator_id)

    def unregister(self, generator_id: str) -> None:
        """Unregister a generator by ID. Cannot unregister built-ins."""
        if generator_id in self._builtin_ids:
            raise ValueError(f"Cannot unregister built-in generator: {generator_id}")
        self._generators.pop(generator_id, None)
        instance = self._instances.pop(generator_id, None)
        if instance and instance.is_loaded():
            asyncio.create_task(instance.unload())

    def is_builtin(self, generator_id: str) -> bool:
        return generator_id in self._builtin_ids

    def get_generator_class(
        self, generator_id: str
    ) -> Optional[Type[BaseGenerator]]:
        return self._generators.get(generator_id)

    def get_generator(
        self,
        generator_id: str,
        config: Optional[GeneratorConfig] = None,
    ) -> Optional[BaseGenerator]:
        """Create a new generator instance (not cached)."""
        generator_class = self._generators.get(generator_id)
        if not generator_class:
            return None
        return generator_class(config)

    def get_cached_instance(self, generator_id: str) -> Optional[BaseGenerator]:
        """Get a cached generator instance (may be loaded)."""
        return self._instances.get(generator_id)

    def cache_instance(self, generator_id: str, instance: BaseGenerator) -> None:
        """Cache a generator instance for reuse."""
        self._instances[generator_id] = instance

    def list_generators(
        self, generator_type: Optional[GeneratorType] = None
    ) -> List[GeneratorCapabilities]:
        """List all registered generators, optionally filtered by type."""
        result = []
        for generator_class in self._generators.values():
            caps = generator_class.get_capabilities()
            if generator_type is None or caps.generator_type == generator_type:
                result.append(caps)
        return result

    def find_compatible(
        self,
        generator_type: GeneratorType,
        vram_available_gb: float,
        resolution: Optional[Tuple[int, int]] = None,
        requires_i2v: bool = False,
        requires_flf: bool = False,
        requires_voice_cloning: bool = False,
        requires_audio_output: bool = False,
    ) -> List[GeneratorCapabilities]:
        """Find generators matching requirements, sorted by preference."""
        compatible = []

        for generator_class in self._generators.values():
            caps = generator_class.get_capabilities()

            if caps.generator_type != generator_type:
                continue
            if caps.vram_gb_min > vram_available_gb:
                continue
            if requires_i2v and not caps.supports_i2v:
                continue
            if requires_flf and not caps.supports_flf:
                continue
            if requires_voice_cloning and not caps.supports_voice_cloning:
                continue
            if requires_audio_output and not caps.produces_audio:
                continue

            if resolution and caps.valid_resolutions:
                if resolution not in caps.valid_resolutions:
                    w, h = resolution
                    sc = caps.shape_constraints
                    if w % sc.width_divisible_by != 0 or h % sc.height_divisible_by != 0:
                        continue

            compatible.append(caps)

        compatible.sort(
            key=lambda c: (c.vram_gb_recommended, -c.max_duration_seconds)
        )
        return compatible

    async def unload_all(self) -> None:
        """Unload all cached generator instances."""
        for instance in list(self._instances.values()):
            if instance.is_loaded():
                try:
                    await instance.unload()
                except Exception:
                    pass
        self._instances.clear()


# Singleton registry
_registry: Optional[GeneratorRegistry] = None


def get_generator_registry() -> GeneratorRegistry:
    """Get the singleton generator registry."""
    global _registry
    if _registry is None:
        _registry = GeneratorRegistry()
    return _registry


# ─────────────────────────────────────────────────────────────────────────────
# RPC Handlers
# ─────────────────────────────────────────────────────────────────────────────

async def handle_ve_list_generators(
    payload: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """RPC handler for listing available generators."""
    registry = get_generator_registry()

    type_str = payload.get("type") if payload else None
    gen_type = GeneratorType(type_str) if type_str else None
    generators = registry.list_generators(gen_type)

    return {
        "success": True,
        "generators": [g.model_dump() for g in generators],
    }


async def handle_ve_get_generator_capabilities(
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    """RPC handler for getting a generator's capabilities."""
    registry = get_generator_registry()

    generator_id = payload.get("generatorId", "")
    if not generator_id:
        return {"success": False, "error": "Generator ID is required"}

    generator_class = registry.get_generator_class(generator_id)
    if not generator_class:
        return {"success": False, "error": f"Generator not found: {generator_id}"}

    capabilities = generator_class.get_capabilities()
    return {
        "success": True,
        "capabilities": capabilities.model_dump(),
    }


async def handle_ve_find_compatible_generators(
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    """RPC handler for finding compatible generators."""
    registry = get_generator_registry()

    type_str = payload.get("type", "")
    vram_available = payload.get("vramAvailableGb", 24.0)
    resolution = payload.get("resolution")
    requires_i2v = payload.get("requiresI2v", False)
    requires_flf = payload.get("requiresFlf", False)
    requires_voice_cloning = payload.get("requiresVoiceCloning", False)
    requires_audio_output = payload.get("requiresAudioOutput", False)

    if not type_str:
        return {"success": False, "error": "Generator type is required"}

    gen_type = GeneratorType(type_str)
    resolution_tuple = tuple(resolution) if resolution else None

    compatible = registry.find_compatible(
        generator_type=gen_type,
        vram_available_gb=vram_available,
        resolution=resolution_tuple,
        requires_i2v=requires_i2v,
        requires_flf=requires_flf,
        requires_voice_cloning=requires_voice_cloning,
        requires_audio_output=requires_audio_output,
    )

    return {
        "success": True,
        "generators": [g.model_dump() for g in compatible],
    }
