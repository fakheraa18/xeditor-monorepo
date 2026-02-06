"""
Zeroscope Text-to-Video Generator

T2V using Zeroscope v2 with optional HD upscaling.
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


class ZeroscopeT2VGenerator(VideoGenerator):
    """
    Text-to-Video generator using Zeroscope v2.
    
    Features:
    - Two-stage generation (base + HD upscaler)
    - Good quality results
    - ~2 second clips
    """

    def __init__(self, config: Optional[GeneratorConfig] = None):
        super().__init__(config)
        self._pipe = None
        self._upscaler = None

    @classmethod
    def get_id(cls) -> str:
        return "t2v_zeroscope"

    @classmethod
    def get_capabilities(cls) -> GeneratorCapabilities:
        return GeneratorCapabilities(
            id="t2v_zeroscope",
            title="Zeroscope v2 (T2V + Upscale)",
            description="Text-to-video with HD upscaling. ~2 second clips.",
            version="1.0.0",
            generator_type=GeneratorType.T2V,
            model_family="zeroscope",
            vram_gb_min=8.0,
            vram_gb_recommended=12.0,
            ram_gb_min=12.0,
            supported_formats=["Landscape"],  # Zeroscope works best in landscape
            supports_i2v=False,
            supports_t2v=True,
            supports_flf=False,
            supports_ip_adapter=False,
            accepts_text_prompt=True,
            accepts_negative_prompt=True,
            valid_resolutions=[
                (576, 320),  # Base resolution
            ],
            max_frames=60,
            max_duration_seconds=2.5,
        )

    async def load(self) -> None:
        """Load the Zeroscope pipelines."""
        if self._loaded:
            return

        try:
            import torch
            from diffusers import DiffusionPipeline, DPMSolverMultistepScheduler

            base_model = self.config.custom.get("model_id", "cerspense/zeroscope_v2_576w")
            upscaler_model = self.config.custom.get("upscaler_id", "cerspense/zeroscope_v2_xl")
            
            print(f"[Zeroscope] Loading base model: {base_model}")
            self._pipe = DiffusionPipeline.from_pretrained(
                base_model,
                torch_dtype=torch.float16,
            )
            self._pipe.scheduler = DPMSolverMultistepScheduler.from_config(
                self._pipe.scheduler.config
            )
            self._pipe.enable_model_cpu_offload()
            
            print(f"[Zeroscope] Loading upscaler: {upscaler_model}")
            self._upscaler = DiffusionPipeline.from_pretrained(
                upscaler_model,
                torch_dtype=torch.float16,
            )
            self._upscaler.scheduler = DPMSolverMultistepScheduler.from_config(
                self._upscaler.scheduler.config
            )
            self._upscaler.enable_model_cpu_offload()
            
            self._loaded = True
            print("[Zeroscope] Models loaded successfully")

        except ImportError:
            raise RuntimeError("diffusers not installed. Install with: pip install diffusers")
        except Exception as e:
            raise RuntimeError(f"Failed to load Zeroscope: {e}")

    async def unload(self) -> None:
        """Unload models and free VRAM."""
        try:
            import torch
            import gc

            if self._pipe is not None:
                del self._pipe
                self._pipe = None
            if self._upscaler is not None:
                del self._upscaler
                self._upscaler = None

            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

        except Exception as e:
            print(f"[Zeroscope] Error unloading: {e}")

        self._loaded = False

    async def generate(
        self,
        output_path: str,
        prompt: Optional[str] = None,
        negative_prompt: Optional[str] = None,
        motion_prompt: Optional[str] = None,
        first_frame_path: Optional[str] = None,
        last_frame_path: Optional[str] = None,
        duration_seconds: float = 2.0,
        fps: int = 24,
        width: int = 576,
        height: int = 320,
        seed: Optional[int] = None,
        steps: Optional[int] = None,
        cfg_scale: Optional[float] = None,
        style_ref: Optional[str] = None,
        character_refs: Optional[List[str]] = None,
        camera_motion: Optional[str] = None,
        preview_mode: bool = False,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> VideoResult:
        """Generate video from text prompt using Zeroscope."""
        
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
                message="Preparing Zeroscope T2V...",
            ))

        try:
            from diffusers.utils import export_to_video

            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            # Calculate frames
            num_frames = int(duration_seconds * fps)
            num_frames = min(num_frames, 60)

            # Default negative prompt
            neg_prompt = negative_prompt or (
                "blurry, low quality, watermark, bad anatomy, text, letters, distorted"
            )

            # Generation parameters
            num_steps = steps or self.config.custom.get("num_inference_steps", 30)
            guidance = cfg_scale or self.config.custom.get("guidance_scale", 9.0)
            upscaler_strength = self.config.custom.get("upscaler_strength", 0.7)

            if preview_mode:
                num_steps = min(num_steps, 15)

            # Base resolution (Zeroscope native)
            base_w, base_h = 576, 320

            if progress_callback:
                await progress_callback(JobProgressEvent(
                    job_id="",
                    seq=0,
                    stage="base_generation",
                    stage_progress=0.2,
                    overall_progress=0.2,
                    message=f"Stage 1: Generating {num_frames} frames at {base_w}x{base_h}...",
                ))

            # Stage 1: Base generation
            video_frames_tensor = self._pipe(
                prompt=prompt,
                negative_prompt=neg_prompt,
                num_inference_steps=num_steps,
                height=base_h,
                width=base_w,
                num_frames=num_frames,
                guidance_scale=guidance,
                output_type="pt",
            ).frames

            if progress_callback:
                await progress_callback(JobProgressEvent(
                    job_id="",
                    seq=0,
                    stage="upscaling",
                    stage_progress=0.6,
                    overall_progress=0.6,
                    message="Stage 2: Upscaling to HD...",
                ))

            # Stage 2: Upscale
            upscaled_frames = self._upscaler(
                prompt=prompt,
                negative_prompt=neg_prompt,
                video=video_frames_tensor,
                strength=upscaler_strength,
                num_inference_steps=num_steps,
                guidance_scale=guidance,
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

            # Export video
            export_to_video(upscaled_frames, output_path, fps=fps)

            if progress_callback:
                await progress_callback(JobProgressEvent(
                    job_id="",
                    seq=0,
                    stage="completed",
                    stage_progress=1.0,
                    overall_progress=1.0,
                    message="Zeroscope video complete",
                ))

            actual_duration = len(upscaled_frames) / fps

            return VideoResult(
                success=True,
                artifact_path=output_path,
                width=1024,  # Upscaled resolution
                height=576,
                fps=float(fps),
                frame_count=len(upscaled_frames),
                duration_seconds=actual_duration,
            )

        except Exception as e:
            return VideoResult(
                success=False,
                error=str(e),
            )
