"""
Wan 2.1 Text-to-Video Generator

Efficient T2V using Wan 2.1 1.3B model.
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


class WanT2VGenerator(VideoGenerator):
    """
    Text-to-Video generator using Wan 2.1 T2V 1.3B model.
    
    Features:
    - Fast generation
    - ~5 second clips
    - Good quality at 480p
    """

    def __init__(self, config: Optional[GeneratorConfig] = None):
        super().__init__(config)
        self._pipe = None

    @classmethod
    def get_id(cls) -> str:
        return "t2v_wan"

    @classmethod
    def get_capabilities(cls) -> GeneratorCapabilities:
        return GeneratorCapabilities(
            id="t2v_wan",
            title="Wan 2.1 T2V (1.3B, Fast)",
            description="Efficient text-to-video. ~5 second clips at 480p.",
            version="1.0.0",
            generator_type="t2v",
            vram_gb_min=15.0,
            vram_gb_recommended=16.0,
            ram_gb_min=12.0,
            supported_formats=["Portrait", "Landscape"],
            supports_i2v=False,
            supports_t2v=True,
            supports_flf=False,
            supports_ip_adapter=False,
            accepts_text_prompt=True,
            accepts_negative_prompt=True,
            valid_resolutions=[
                (832, 480),  # Landscape
                (480, 832),  # Portrait
            ],
            max_frames=120,
            max_duration_seconds=5.0,
        )

    async def load(self) -> None:
        """Load the Wan T2V pipeline."""
        if self._loaded:
            return

        try:
            import torch
            from diffusers import WanPipeline, AutoencoderKLWan

            model_id = self.config.custom.get("model_id", "Wan-AI/Wan2.1-T2V-1.3B-Diffusers")
            
            print(f"[WanT2V] Loading model: {model_id}")
            
            # Load VAE separately (works better in float32)
            vae = AutoencoderKLWan.from_pretrained(
                model_id,
                subfolder="vae",
                torch_dtype=torch.float32,
            )
            
            # Load main pipeline
            self._pipe = WanPipeline.from_pretrained(
                model_id,
                vae=vae,
                torch_dtype=torch.bfloat16,
            )
            self._pipe.enable_model_cpu_offload()
            
            self._loaded = True
            print("[WanT2V] Model loaded successfully")

        except ImportError:
            raise RuntimeError("diffusers not installed. Install with: pip install diffusers")
        except Exception as e:
            raise RuntimeError(f"Failed to load Wan T2V: {e}")

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
            print(f"[WanT2V] Error unloading: {e}")

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
        fps: int = 24,
        width: int = 832,
        height: int = 480,
        seed: Optional[int] = None,
        steps: Optional[int] = None,
        cfg_scale: Optional[float] = None,
        style_ref: Optional[str] = None,
        character_refs: Optional[List[str]] = None,
        camera_motion: Optional[str] = None,
        preview_mode: bool = False,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> VideoResult:
        """Generate video from text prompt using Wan T2V."""
        
        if not prompt:
            return VideoResult(
                success=False,
                error="Text prompt is required for T2V generation",
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
                message="Preparing T2V generation...",
            ))

        try:
            from diffusers.utils import export_to_video

            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            # Calculate number of frames
            num_frames = int(duration_seconds * fps)
            num_frames = min(num_frames, 120)  # Cap at model max

            # Default negative prompt
            neg_prompt = negative_prompt or (
                "Bright tones, overexposed, static, blurred details, subtitles, "
                "worst quality, low quality, JPEG compression residue, ugly, "
                "incomplete, extra fingers, poorly drawn hands, poorly drawn faces, "
                "deformed, disfigured, misshapen limbs, fused fingers, still picture, "
                "messy background, walking backwards"
            )

            # Generation parameters
            num_steps = steps or self.config.custom.get("num_inference_steps", 30)
            guidance = cfg_scale or self.config.custom.get("guidance_scale", 5.0)

            if preview_mode:
                num_steps = min(num_steps, 15)
                num_frames = min(num_frames, 30)

            if progress_callback:
                await progress_callback(JobProgressEvent(
                    job_id="",
                    seq=0,
                    stage="generating",
                    stage_progress=0.3,
                    overall_progress=0.3,
                    message=f"Generating {num_frames} frames...",
                ))

            # Generate video
            video_frames = self._pipe(
                prompt=prompt,
                negative_prompt=neg_prompt,
                height=height,
                width=width,
                num_frames=num_frames,
                guidance_scale=guidance,
                num_inference_steps=num_steps,
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
            export_to_video(video_frames, output_path, fps=fps)

            if progress_callback:
                await progress_callback(JobProgressEvent(
                    job_id="",
                    seq=0,
                    stage="completed",
                    stage_progress=1.0,
                    overall_progress=1.0,
                    message="Wan T2V video complete",
                ))

            actual_duration = len(video_frames) / fps

            return VideoResult(
                success=True,
                artifact_path=output_path,
                width=width,
                height=height,
                fps=float(fps),
                frame_count=len(video_frames),
                duration_seconds=actual_duration,
            )

        except Exception as e:
            return VideoResult(
                success=False,
                error=str(e),
            )
