"""
Base Generator Classes and Registry

This module defines the abstract base classes for all generator types
and the registry for discovering and managing generators.
"""

import abc
import asyncio
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import (
    Any,
    AsyncGenerator,
    Callable,
    Dict,
    List,
    Optional,
    Tuple,
    Type,
    TypeVar,
)

from apps.video_editor.models import (
    GeneratorCapabilities,
    GeneratorConfig,
    JobProgressEvent,
    AssetRef,
)


# Type for progress callback
ProgressCallback = Callable[[JobProgressEvent], Any]


@dataclass
class GenerationResult:
    """Result from a generation operation."""
    success: bool
    artifact_path: Optional[str] = None
    artifact_paths: Optional[List[str]] = None
    duration_seconds: Optional[float] = None
    width: Optional[int] = None
    height: Optional[int] = None
    error: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None


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
class LLMResult:
    """Result from LLM generation."""
    success: bool
    content: str = ""
    finish_reason: Optional[str] = None
    usage: Optional[Dict[str, int]] = None
    error: Optional[str] = None


# ─────────────────────────────────────────────────────────────────────────────
# Base Generator Class
# ─────────────────────────────────────────────────────────────────────────────

class BaseGenerator(abc.ABC):
    """
    Abstract base class for all generators.
    
    Generators are stateless services that:
    1. Declare their capabilities
    2. Receive inputs and produce outputs
    3. Manage VRAM lifecycle (load/unload)
    4. Report progress via callbacks
    """

    def __init__(self, config: Optional[GeneratorConfig] = None):
        self.config = config or GeneratorConfig(generator_id=self.get_id())
        self._loaded = False

    @classmethod
    @abc.abstractmethod
    def get_id(cls) -> str:
        """Get the unique identifier for this generator."""
        ...

    @classmethod
    @abc.abstractmethod
    def get_capabilities(cls) -> GeneratorCapabilities:
        """Get the capabilities of this generator."""
        ...

    @abc.abstractmethod
    async def load(self) -> None:
        """
        Load the model into VRAM/memory.
        
        Called before generation starts. Should be idempotent.
        """
        ...

    @abc.abstractmethod
    async def unload(self) -> None:
        """
        Unload the model from VRAM/memory.
        
        Called after generation completes or on error.
        Should clear GPU memory aggressively.
        """
        ...

    def is_loaded(self) -> bool:
        """Check if the model is currently loaded."""
        return self._loaded

    async def __aenter__(self) -> "BaseGenerator":
        """Context manager entry - load model."""
        await self.load()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit - unload model."""
        await self.unload()

    def validate_config(self) -> List[str]:
        """
        Validate the current configuration.
        
        Returns:
            List of validation error messages (empty if valid)
        """
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
        """
        Generate text from the LLM.
        
        Args:
            prompt: The user prompt
            system_prompt: Optional system prompt
            max_tokens: Maximum tokens to generate
            temperature: Sampling temperature
            progress_callback: Optional callback for streaming progress
            
        Returns:
            LLMResult with the generated text
        """
        ...

    async def generate_stream(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
    ) -> AsyncGenerator[str, None]:
        """
        Stream text generation.
        
        Yields:
            Text chunks as they are generated
        """
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
        """
        Generate speech from text.
        
        Args:
            text: Text to synthesize
            output_path: Path to save the audio file
            voice_sample_path: Optional path to voice sample for cloning
            language: Language code
            speed: Speech speed multiplier
            emotion: Optional emotion hint
            progress_callback: Optional callback for progress
            
        Returns:
            TTSResult with audio file path and duration
        """
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
        preview_mode: bool = False,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> ImageResult:
        """
        Generate an image from text.
        
        Args:
            prompt: Text prompt for the image
            output_path: Path to save the image
            negative_prompt: Negative prompt
            width: Image width
            height: Image height
            seed: Random seed for reproducibility
            steps: Number of inference steps
            cfg_scale: Classifier-free guidance scale
            style_ref: Path to style reference image
            character_refs: Paths to character reference images (IP-adapter)
            preview_mode: If True, generate fast low-quality preview
            progress_callback: Optional callback for progress
            
        Returns:
            ImageResult with image path and metadata
        """
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
        camera_motion: Optional[str] = None,
        preview_mode: bool = False,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> VideoResult:
        """
        Generate a video.
        
        Args:
            output_path: Path to save the video
            prompt: Text prompt (for T2V or motion guidance)
            negative_prompt: Negative prompt
            motion_prompt: Motion-specific prompt
            first_frame_path: First frame image (for I2V or FLF)
            last_frame_path: Last frame image (for FLF interpolation)
            duration_seconds: Target video duration
            fps: Frames per second
            width: Video width
            height: Video height
            seed: Random seed
            steps: Inference steps
            cfg_scale: CFG scale
            style_ref: Style reference image path
            character_refs: Character reference image paths
            camera_motion: Camera motion preset/description
            preview_mode: If True, generate fast low-quality preview
            progress_callback: Optional callback for progress
            
        Returns:
            VideoResult with video path and metadata
        """
        ...


class MusicGenerator(BaseGenerator):
    """Base class for music/SFX generators."""

    @abc.abstractmethod
    async def generate(
        self,
        prompt: str,
        output_path: str,
        duration_seconds: float = 30.0,
        seed: Optional[int] = None,
        temperature: float = 1.0,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> GenerationResult:
        """
        Generate music or sound effects.
        
        Args:
            prompt: Description of the music/sound
            output_path: Path to save the audio
            duration_seconds: Target duration
            seed: Random seed
            temperature: Generation temperature
            progress_callback: Optional callback for progress
            
        Returns:
            GenerationResult with audio path
        """
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
        """
        Upscale an image or video.
        
        Args:
            input_path: Path to input file
            output_path: Path to save output
            scale_factor: Upscaling factor
            denoise: Whether to apply denoising
            progress_callback: Optional callback for progress
            
        Returns:
            GenerationResult with output path
        """
        ...


# ─────────────────────────────────────────────────────────────────────────────
# Generator Registry
# ─────────────────────────────────────────────────────────────────────────────

T = TypeVar("T", bound=BaseGenerator)


class GeneratorRegistry:
    """
    Registry for discovering and managing generator plugins.
    
    Generators can be registered programmatically or discovered
    from a plugins directory.
    """

    def __init__(self):
        self._generators: Dict[str, Type[BaseGenerator]] = {}
        self._instances: Dict[str, BaseGenerator] = {}

    def register(self, generator_class: Type[BaseGenerator]) -> None:
        """
        Register a generator class.
        
        Args:
            generator_class: The generator class to register
        """
        generator_id = generator_class.get_id()
        self._generators[generator_id] = generator_class

    def unregister(self, generator_id: str) -> None:
        """Unregister a generator by ID."""
        self._generators.pop(generator_id, None)
        instance = self._instances.pop(generator_id, None)
        if instance and instance.is_loaded():
            asyncio.create_task(instance.unload())

    def get_generator_class(self, generator_id: str) -> Optional[Type[BaseGenerator]]:
        """Get a generator class by ID."""
        return self._generators.get(generator_id)

    def get_generator(
        self,
        generator_id: str,
        config: Optional[GeneratorConfig] = None
    ) -> Optional[BaseGenerator]:
        """
        Get or create a generator instance.
        
        Args:
            generator_id: ID of the generator
            config: Optional configuration for the generator
            
        Returns:
            Generator instance or None if not found
        """
        generator_class = self._generators.get(generator_id)
        if not generator_class:
            return None
        
        # Create new instance with config
        return generator_class(config)

    def get_cached_instance(self, generator_id: str) -> Optional[BaseGenerator]:
        """Get a cached generator instance (may be loaded)."""
        return self._instances.get(generator_id)

    def list_generators(self, generator_type: Optional[str] = None) -> List[GeneratorCapabilities]:
        """
        List all registered generators.
        
        Args:
            generator_type: Filter by type (e.g., "llm", "tts", "t2i")
            
        Returns:
            List of generator capabilities
        """
        result = []
        for generator_class in self._generators.values():
            caps = generator_class.get_capabilities()
            if generator_type is None or caps.generator_type == generator_type:
                result.append(caps)
        return result

    def list_by_type(self, generator_type: str) -> List[GeneratorCapabilities]:
        """List generators of a specific type."""
        return self.list_generators(generator_type)

    def find_compatible(
        self,
        generator_type: str,
        vram_available_gb: float,
        resolution: Optional[Tuple[int, int]] = None,
        requires_i2v: bool = False,
        requires_flf: bool = False,
        requires_voice_cloning: bool = False,
    ) -> List[GeneratorCapabilities]:
        """
        Find generators that match the given requirements.
        
        Args:
            generator_type: Type of generator needed
            vram_available_gb: Available VRAM in GB
            resolution: Required resolution (width, height)
            requires_i2v: Must support image-to-video
            requires_flf: Must support first+last frame
            requires_voice_cloning: Must support voice cloning
            
        Returns:
            List of compatible generator capabilities, sorted by preference
        """
        compatible = []
        
        for generator_class in self._generators.values():
            caps = generator_class.get_capabilities()
            
            # Filter by type
            if caps.generator_type != generator_type:
                continue
            
            # Filter by VRAM
            if caps.vram_gb_min > vram_available_gb:
                continue
            
            # Filter by capabilities
            if requires_i2v and not caps.supports_i2v:
                continue
            if requires_flf and not caps.supports_flf:
                continue
            if requires_voice_cloning and not caps.supports_voice_cloning:
                continue
            
            # Filter by resolution
            if resolution and caps.valid_resolutions:
                if resolution not in caps.valid_resolutions:
                    # Check if resolution is compatible (divisibility)
                    w, h = resolution
                    div = caps.resolution_must_be_divisible_by
                    if w % div != 0 or h % div != 0:
                        continue
            
            compatible.append(caps)
        
        # Sort by: recommended VRAM (prefer lower), then by capabilities
        compatible.sort(key=lambda c: (c.vram_gb_recommended, -c.max_duration_seconds))
        
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

async def handle_ve_list_generators(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """RPC handler for listing available generators."""
    registry = get_generator_registry()
    
    generator_type = payload.get("type") if payload else None
    generators = registry.list_generators(generator_type)
    
    return {
        "success": True,
        "generators": [g.model_dump() for g in generators],
    }


async def handle_ve_get_generator_capabilities(payload: Dict[str, Any]) -> Dict[str, Any]:
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


async def handle_ve_find_compatible_generators(payload: Dict[str, Any]) -> Dict[str, Any]:
    """RPC handler for finding compatible generators."""
    registry = get_generator_registry()
    
    generator_type = payload.get("type", "")
    vram_available = payload.get("vramAvailableGb", 24.0)
    resolution = payload.get("resolution")
    requires_i2v = payload.get("requiresI2v", False)
    requires_flf = payload.get("requiresFlf", False)
    requires_voice_cloning = payload.get("requiresVoiceCloning", False)
    
    if not generator_type:
        return {"success": False, "error": "Generator type is required"}
    
    resolution_tuple = tuple(resolution) if resolution else None
    
    compatible = registry.find_compatible(
        generator_type=generator_type,
        vram_available_gb=vram_available,
        resolution=resolution_tuple,
        requires_i2v=requires_i2v,
        requires_flf=requires_flf,
        requires_voice_cloning=requires_voice_cloning,
    )
    
    return {
        "success": True,
        "generators": [g.model_dump() for g in compatible],
    }
