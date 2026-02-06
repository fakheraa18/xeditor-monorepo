"""
Stable Diffusion XL Text-to-Image Generator

A high-quality T2I generator using SDXL with optional refiner.
"""

import os
from typing import List, Optional

from apps.video_editor.generators.base import (
    ImageGenerator,
    ImageResult,
    ProgressCallback,
    JobProgressEvent,
)
from apps.video_editor.models import GeneratorCapabilities, GeneratorConfig, GeneratorType, ShapeConstraints


class SDXLT2IGenerator(ImageGenerator):
    """
    Text-to-Image generator using Stable Diffusion XL.
    
    Features:
    - High quality 1024x1024 base generation
    - Optional refiner for enhanced details
    - IP-Adapter support (placeholder)
    - LoRA support (placeholder)
    """

    def __init__(self, config: Optional[GeneratorConfig] = None):
        super().__init__(config)
        self._pipe = None
        self._refiner = None

    @classmethod
    def get_id(cls) -> str:
        return "t2i_sdxl"

    @classmethod
    def get_capabilities(cls) -> GeneratorCapabilities:
        return GeneratorCapabilities(
            id="t2i_sdxl",
            title="SDXL + Refiner (High Quality)",
            description="Stable Diffusion XL with optional refiner for high-quality image generation.",
            version="1.0.0",
            generator_type=GeneratorType.T2I,
            vram_gb_min=10.0,
            vram_gb_recommended=16.0,
            ram_gb_min=16.0,
            supported_formats=["Portrait", "Landscape", "Square"],
            supports_ip_adapter=True,
            supports_lora=True,
            max_subjects=2,
            accepts_text_prompt=True,
            accepts_negative_prompt=True,
            model_family="sdxl",
            valid_resolutions=[
                (1024, 1024),  # Square
                (1152, 896),   # Landscape
                (896, 1152),   # Portrait
                (1344, 768),   # Wide landscape
                (768, 1344),   # Tall portrait
            ],
            best_resolutions=[(1024, 1024), (1152, 896), (896, 1152)],
            shape_constraints=ShapeConstraints(
                width_divisible_by=8,
                height_divisible_by=8,
            ),
            produces_video=False,
        )

    async def load(self) -> None:
        """Load the SDXL pipeline."""
        if self._loaded:
            return

        try:
            import torch
            from diffusers import StableDiffusionXLPipeline, DiffusionPipeline

            device = "cuda" if torch.cuda.is_available() else "cpu"
            dtype = torch.float16 if torch.cuda.is_available() else torch.float32
            
            model_id = self.config.custom.get("model_id", "stabilityai/stable-diffusion-xl-base-1.0")
            refiner_id = self.config.custom.get("refiner_id", "stabilityai/stable-diffusion-xl-refiner-1.0")
            use_refiner = self.config.custom.get("use_refiner", True)

            print(f"[SDXL] Loading base model: {model_id}")
            self._pipe = StableDiffusionXLPipeline.from_pretrained(
                model_id,
                torch_dtype=dtype,
                variant="fp16" if dtype == torch.float16 else None,
                use_safetensors=True,
            ).to(device)
            
            if use_refiner and refiner_id:
                print(f"[SDXL] Loading refiner: {refiner_id}")
                self._refiner = DiffusionPipeline.from_pretrained(
                    refiner_id,
                    text_encoder_2=self._pipe.text_encoder_2,
                    vae=self._pipe.vae,
                    torch_dtype=dtype,
                    variant="fp16" if dtype == torch.float16 else None,
                    use_safetensors=True,
                ).to(device)

            self._loaded = True
            print("[SDXL] Models loaded successfully")

        except ImportError:
            raise RuntimeError("diffusers not installed. Install with: pip install diffusers")
        except Exception as e:
            raise RuntimeError(f"Failed to load SDXL: {e}")

    async def unload(self) -> None:
        """Unload models and free VRAM."""
        try:
            import torch
            import gc

            if self._pipe is not None:
                del self._pipe
                self._pipe = None
            if self._refiner is not None:
                del self._refiner
                self._refiner = None

            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

        except Exception as e:
            print(f"[SDXL] Error unloading: {e}")

        self._loaded = False

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
        """Generate an image from text prompt."""
        if not self._loaded:
            await self.load()

        if progress_callback:
            await progress_callback(JobProgressEvent(
                job_id="",
                seq=0,
                stage="generating_image",
                stage_progress=0.1,
                overall_progress=0.1,
                message=f"Generating image: {prompt[:50]}...",
            ))

        try:
            import torch

            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            # Set up generator for seed
            generator = None
            actual_seed = seed
            if seed is not None and seed != -1:
                generator = torch.Generator(device=self._pipe.device).manual_seed(seed)
            else:
                actual_seed = torch.randint(0, 2**32, (1,)).item()
                generator = torch.Generator(device=self._pipe.device).manual_seed(actual_seed)

            # Generation parameters
            num_steps = steps or self.config.custom.get("num_inference_steps", 30)
            guidance = cfg_scale or self.config.custom.get("guidance_scale", 7.5)
            
            if preview_mode:
                num_steps = min(num_steps, 15)

            neg_prompt = negative_prompt or "worst quality, low quality, bad anatomy, text, watermark, blurry"

            # Base generation
            gen_kwargs = {
                "prompt": prompt,
                "negative_prompt": neg_prompt,
                "width": width,
                "height": height,
                "num_inference_steps": num_steps,
                "guidance_scale": guidance,
                "generator": generator,
            }

            if self._refiner and not preview_mode:
                gen_kwargs["output_type"] = "latent"
                gen_kwargs["denoising_end"] = 0.8

            if progress_callback:
                await progress_callback(JobProgressEvent(
                    job_id="",
                    seq=0,
                    stage="base_generation",
                    stage_progress=0.3,
                    overall_progress=0.3,
                    message="Running base generation...",
                ))

            image = self._pipe(**gen_kwargs).images[0]

            # Refine if available
            if self._refiner and not preview_mode:
                if progress_callback:
                    await progress_callback(JobProgressEvent(
                        job_id="",
                        seq=0,
                        stage="refining",
                        stage_progress=0.7,
                        overall_progress=0.7,
                        message="Refining image...",
                    ))

                refiner_kwargs = {
                    "prompt": prompt,
                    "negative_prompt": neg_prompt,
                    "image": image,
                    "denoising_start": 0.8,
                    "num_inference_steps": num_steps,
                    "generator": generator,
                }
                image = self._refiner(**refiner_kwargs).images[0]

            # Save image
            image.save(output_path)

            if progress_callback:
                await progress_callback(JobProgressEvent(
                    job_id="",
                    seq=0,
                    stage="completed",
                    stage_progress=1.0,
                    overall_progress=1.0,
                    message="Image generation complete",
                ))

            return ImageResult(
                success=True,
                artifact_path=output_path,
                width=width,
                height=height,
                seed=actual_seed,
            )

        except Exception as e:
            return ImageResult(
                success=False,
                error=str(e),
            )
