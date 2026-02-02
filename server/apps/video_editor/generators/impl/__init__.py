"""
Video Editor Generator Implementations

This package contains the concrete generator implementations for the video editor.
"""

from apps.video_editor.generators.impl.tts_coqui_xtts import CoquiXTTSGenerator
from apps.video_editor.generators.impl.t2i_sdxl import SDXLT2IGenerator
from apps.video_editor.generators.impl.i2v_slideshow import SlideshowI2VGenerator
from apps.video_editor.generators.impl.i2v_svd import SVDI2VGenerator
from apps.video_editor.generators.impl.t2v_wan import WanT2VGenerator
from apps.video_editor.generators.impl.t2v_zeroscope import ZeroscopeT2VGenerator
from apps.video_editor.generators.impl.story_llm import StoryLLMGenerator

__all__ = [
    "CoquiXTTSGenerator",
    "SDXLT2IGenerator",
    "SlideshowI2VGenerator",
    "SVDI2VGenerator",
    "WanT2VGenerator",
    "ZeroscopeT2VGenerator",
    "StoryLLMGenerator",
]
