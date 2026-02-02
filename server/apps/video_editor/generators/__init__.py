"""
Video Editor Generator Plugin System

This package provides the extensible generator framework for:
- LLM (story generation)
- TTS (text-to-speech)
- T2I (text-to-image)
- I2V (image-to-video)
- T2V (text-to-video)
- Music/SFX generation
- Upscaling/post-processing
"""

from apps.video_editor.generators.base import (
    BaseGenerator,
    LLMGenerator,
    TTSGenerator,
    ImageGenerator,
    VideoGenerator,
    MusicGenerator,
    UpscalerGenerator,
    GeneratorRegistry,
    get_generator_registry,
)

__all__ = [
    "BaseGenerator",
    "LLMGenerator",
    "TTSGenerator",
    "ImageGenerator",
    "VideoGenerator",
    "MusicGenerator",
    "UpscalerGenerator",
    "GeneratorRegistry",
    "get_generator_registry",
]
