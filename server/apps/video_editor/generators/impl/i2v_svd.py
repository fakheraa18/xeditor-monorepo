"""
Stable Video Diffusion Image-to-Video Generator

High quality I2V using Stability AI's SVD model.
"""

import os
from typing import List, Optional

from apps.video_editor.generators.base import (
    VideoGenerator,
    VideoResult,
    ProgressCallback,
    JobProgressEvent,
)
from apps.video_editor.models import GeneratorCapabilities, GeneratorConfig


class SVDI2VGenerator(VideoGenerator):
    """
    Image-to-Video generator using Stable Video Diffusion.
    
    Features:
    - High quality video from single image
    - Motion bucket control
    - ~2 second clips at native 25 frames
    """

    def __init__(self, config: Optional[GeneratorConfig] = None):
        super().__init__(config)
        self._pipe = None

    @classmethod
    def get_id(cls) -> str:
        return "i2v_svd"

    @classmethod
    def get_capabilities(cls) -> GeneratorCapabilities:
        return GeneratorCapabilities(
            id="i2v_svd",
            title="Stable Video Diffusion (I2V)",
            description="High-quality image-to-video using SVD. ~2 second clips.",
            version="1.0.0",
            generator_type="i2v",
            vram_gb_min=8.0,
            vram_gb_recommended=12.0,
            ram_gb_min=12.0,
            supported_formats=["Portrait", "Landscape"],
            supports_i2v=True,
            supports_t2v=False,
            supports_flf=False,
            supports_ip_adapter=False,
            accepts_text_prompt=False,  # SVD doesn't use text prompts
            accepts_negative_prompt=False,
            valid_resolutions=[
                (1024, 576),  # Landscape
                (576, 1024),  # Portrait
            ],
            max_frames=25,
            max_duration_seconds=2.5,
        )

    async def load(self) -> None:
        """Load the SVD pipeline."""
        if self._loaded:
            return

        try:
            import torch
            from diffusers import StableVideoDiffusionPipeline

            model_id = self.config.custom.get("model_id", "stabilityai/stable-video-diffusion-img2vid-xt")
            
            print(f"[SVD] Loading model: {model_id}")
            self._pipe = StableVideoDiffusionPipeline.from_pretrained(
                model_id,
                torch_dtype=torch.float16,
            )
            self._pipe.enable_model_cpu_offload()
            
            self._loaded = True
            print("[SVD] Model loaded successfully")

        except ImportError:
            raise RuntimeError("diffusers not installed. Install with: pip install diffusers")
        except Exception as e:
            raise RuntimeError(f"Failed to load SVD: {e}")

    async def unload(self) -> None:
        """Unload model and free VRAM."""
        try:
            import torch
            import gc

            if self._pipe is not None:
                del self._pipe
                self._pipe = None

            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

        except Exception as e:
            print(f"[SVD] Error unloading: {e}")

        self._loaded = False

    def _resize_and_pad(self, image, target_width: int, target_height: int):
        """Resize and pad image to target dimensions."""
        from PIL import Image
        
        original_aspect = image.width / image.height
        target_aspect = target_width / target_height
        
        if original_aspect > target_aspect:
            new_width = target_width
            new_height = int(target_width / original_aspect)
        else:
            new_height = target_height
            new_width = int(target_height * original_aspect)
        
        resized = image.resize((new_width, new_height), Image.LANCZOS)
        
        # Create black background and paste centered
        background = Image.new('RGB', (target_width, target_height), (0, 0, 0))
        x = (target_width - new_width) // 2
        y = (target_height - new_height) // 2
        background.paste(resized, (x, y))
        
        return background

    async def generate(
        self,
        output_path: str,
        prompt: Optional[str] = None,
        negative_prompt: Optional[str] = None,
        motion_prompt: Optional[str] = None,
        first_frame_path: Optional[str] = None,
        last_frame_path: Optional[str] = None,
        duration_seconds: float = 2.0,
        fps: int = 12,
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
        """Generate video from image using SVD."""
        
        if not first_frame_path or not os.path.exists(first_frame_path):
            return VideoResult(
                success=False,
                error="First frame image is required for I2V generation",
            )

        if not self._loaded:
            await self.load()

        if progress_callback:
            await progress_callback(JobProgressEvent(
                job_id="",
                seq=0,
                stage="preparing",
                stage_progress=0.1,
                overall_progress=0.1,
                message="Preparing image for SVD...",
            ))

        try:
            from diffusers.utils import load_image, export_to_video

            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            # Load and prepare image
            input_image = load_image(first_frame_path)
            
            # Determine target resolution based on aspect ratio
            if input_image.width > input_image.height:
                target_w, target_h = 1024, 576
            else:
                target_w, target_h = 576, 1024
            
            prepared_image = self._resize_and_pad(input_image, target_w, target_h)

            # SVD generates 25 frames natively
            num_frames = 25
            
            # Calculate FPS to match target duration
            calculated_fps = max(1, round(num_frames / duration_seconds)) if duration_seconds > 0 else 12

            # Motion bucket control (0-255, higher = more motion)
            motion_bucket_id = self.config.custom.get("motion_bucket_id", 127)
            
            # Adjust based on motion prompt hints
            if motion_prompt:
                mp_lower = motion_prompt.lower()
                if any(w in mp_lower for w in ['fast', 'quick', 'rapid', 'zoom', 'pan']):
                    motion_bucket_id = min(255, motion_bucket_id + 50)
                elif any(w in mp_lower for w in ['slow', 'gentle', 'subtle', 'still']):
                    motion_bucket_id = max(0, motion_bucket_id - 50)

            if progress_callback:
                await progress_callback(JobProgressEvent(
                    job_id="",
                    seq=0,
                    stage="generating",
                    stage_progress=0.3,
                    overall_progress=0.3,
                    message="Generating video frames...",
                ))

            # Generate video
            video_frames = self._pipe(
                image=prepared_image,
                height=target_h,
                width=target_w,
                decode_chunk_size=self.config.custom.get("decode_chunk_size", 8),
                num_frames=num_frames,
                motion_bucket_id=motion_bucket_id,
                noise_aug_strength=self.config.custom.get("noise_aug_strength", 0.02),
            ).frames[0]

            if progress_callback:
                await progress_callback(JobProgressEvent(
                    job_id="",
                    seq=0,
                    stage="exporting",
                    stage_progress=0.9,
                    overall_progress=0.9,
                    message="Exporting video...",
                ))

            # Export to video file
            export_to_video(video_frames, output_path, fps=calculated_fps)

            if progress_callback:
                await progress_callback(JobProgressEvent(
                    job_id="",
                    seq=0,
                    stage="completed",
                    stage_progress=1.0,
                    overall_progress=1.0,
                    message="SVD video complete",
                ))

            actual_duration = num_frames / calculated_fps

            return VideoResult(
                success=True,
                artifact_path=output_path,
                width=target_w,
                height=target_h,
                fps=float(calculated_fps),
                frame_count=num_frames,
                duration_seconds=actual_duration,
            )

        except Exception as e:
            return VideoResult(
                success=False,
                error=str(e),
            )
