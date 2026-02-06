"""
Video Editor Generator Plugin System (v2)

Extensible generator framework for:
- LLM (story/script generation)
- TTS (text-to-speech)
- T2I (text-to-image)
- I2V (image-to-video)
- T2V (text-to-video)
- AV (joint audio+video, e.g. LTX-2)
- Music generation
- SFX generation
- LipSync (audio-driven lip sync)
- Upscaling/post-processing
"""

from apps.video_editor.generators.base import (
    BaseGenerator,
    LLMGenerator,
    TTSGenerator,
    ImageGenerator,
    VideoGenerator,
    AudioVideoGenerator,
    MusicGenerator,
    SFXGenerator,
    LipSyncGenerator,
    UpscalerGenerator,
    GeneratorRegistry,
    get_generator_registry,
    validate_shape,
    # Result types
    GenerationResult,
    LLMResult,
    TTSResult,
    ImageResult,
    VideoResult,
    AudioVideoResult,
    LipSyncResult,
    # Callback
    ProgressCallback,
)

__all__ = [
    "BaseGenerator",
    "LLMGenerator",
    "TTSGenerator",
    "ImageGenerator",
    "VideoGenerator",
    "AudioVideoGenerator",
    "MusicGenerator",
    "SFXGenerator",
    "LipSyncGenerator",
    "UpscalerGenerator",
    "GeneratorRegistry",
    "get_generator_registry",
    "validate_shape",
    "GenerationResult",
    "LLMResult",
    "TTSResult",
    "ImageResult",
    "VideoResult",
    "AudioVideoResult",
    "LipSyncResult",
    "ProgressCallback",
]
