"""
Slideshow Image-to-Video Generator

A simple, fast I2V generator that creates a video from a static image.
Uses no AI/GPU - just holds the image for the specified duration.
Great for placeholders or simple slideshow-style videos.
"""

import os
from typing import List, Optional

from apps.video_editor.generators.base import (
    VideoGenerator,
    VideoResult,
    ProgressCallback,
    JobProgressEvent,
)
from apps.video_editor.models import GeneratorCapabilities, GeneratorConfig, GeneratorType


class SlideshowI2VGenerator(VideoGenerator):
    """
    Simple I2V generator that creates a video from a static image.
    
    Features:
    - Very fast (no AI required)
    - Minimal resource usage
    - Works with any resolution
    - Perfect for placeholders or slideshows
    """

    def __init__(self, config: Optional[GeneratorConfig] = None):
        super().__init__(config)

    @classmethod
    def get_id(cls) -> str:
        return "i2v_slideshow"

    @classmethod
    def get_capabilities(cls) -> GeneratorCapabilities:
        return GeneratorCapabilities(
            id="i2v_slideshow",
            title="Slideshow (Static Image)",
            description="Creates video from static image. Very fast, no GPU required.",
            version="1.0.0",
            generator_type=GeneratorType.I2V,
            vram_gb_min=0.1,  # Virtually no VRAM needed
            vram_gb_recommended=0.5,
            ram_gb_min=1.0,
            supported_formats=["Portrait", "Landscape", "Square"],
            supports_i2v=True,
            supports_t2v=False,
            supports_flf=False,
            accepts_text_prompt=False,  # Ignores prompts
            accepts_negative_prompt=False,
            max_duration_seconds=60.0,  # Can be very long
        )

    async def load(self) -> None:
        """No model to load."""
        self._loaded = True

    async def unload(self) -> None:
        """No model to unload."""
        self._loaded = False

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
        """Create a video from a static image."""
        
        if not first_frame_path or not os.path.exists(first_frame_path):
            return VideoResult(
                success=False,
                error="First frame image is required for slideshow generation",
            )

        if progress_callback:
            await progress_callback(JobProgressEvent(
                job_id="",
                seq=0,
                stage="creating_slideshow",
                stage_progress=0.2,
                overall_progress=0.2,
                message=f"Creating {duration_seconds:.1f}s slideshow video...",
            ))

        try:
            from moviepy.video.VideoClip import ImageClip

            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            # Create video from static image
            video_clip = ImageClip(first_frame_path).with_duration(duration_seconds)

            if progress_callback:
                await progress_callback(JobProgressEvent(
                    job_id="",
                    seq=0,
                    stage="encoding",
                    stage_progress=0.5,
                    overall_progress=0.5,
                    message="Encoding video...",
                ))

            # Write video file
            video_clip.write_videofile(
                output_path,
                fps=fps,
                codec="libx264",
                audio=False,
                threads=4,
                preset="medium",
                logger=None,  # Suppress verbose logs
            )

            video_clip.close()

            if progress_callback:
                await progress_callback(JobProgressEvent(
                    job_id="",
                    seq=0,
                    stage="completed",
                    stage_progress=1.0,
                    overall_progress=1.0,
                    message="Slideshow video complete",
                ))

            # Get actual dimensions from the image
            from PIL import Image
            with Image.open(first_frame_path) as img:
                actual_width, actual_height = img.size

            return VideoResult(
                success=True,
                artifact_path=output_path,
                width=actual_width,
                height=actual_height,
                fps=float(fps),
                frame_count=int(duration_seconds * fps),
                duration_seconds=duration_seconds,
            )

        except ImportError as e:
            return VideoResult(
                success=False,
                error=f"Required library not installed: {e}. Install moviepy with: pip install moviepy",
            )
        except Exception as e:
            return VideoResult(
                success=False,
                error=str(e),
            )
