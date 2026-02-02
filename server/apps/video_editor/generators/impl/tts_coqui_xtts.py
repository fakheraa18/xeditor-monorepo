"""
Coqui XTTS Text-to-Speech Generator

A TTS generator using Coqui's XTTS v2 model for high-quality
multi-lingual speech synthesis with optional voice cloning.
"""

import os
from typing import Optional

from apps.video_editor.generators.base import (
    TTSGenerator,
    TTSResult,
    ProgressCallback,
    JobProgressEvent,
)
from apps.video_editor.models import GeneratorCapabilities, GeneratorConfig


class CoquiXTTSGenerator(TTSGenerator):
    """
    Text-to-Speech generator using Coqui XTTS v2.
    
    Features:
    - Multi-language support (17+ languages)
    - Voice cloning from a reference sample
    - High quality documentary-style output
    """

    def __init__(self, config: Optional[GeneratorConfig] = None):
        super().__init__(config)
        self._tts = None

    @classmethod
    def get_id(cls) -> str:
        return "tts_coqui_xtts"

    @classmethod
    def get_capabilities(cls) -> GeneratorCapabilities:
        return GeneratorCapabilities(
            id="tts_coqui_xtts",
            title="Coqui XTTS v2 (Multi-Language, Voice Cloning)",
            description="High-quality TTS with voice cloning support. Supports 17+ languages.",
            version="1.0.0",
            generator_type="tts",
            vram_gb_min=2.0,
            vram_gb_recommended=4.0,
            ram_gb_min=8.0,
            supports_voice_cloning=True,
            supported_languages=[
                "en", "es", "fr", "de", "it", "pt", "pl", "tr",
                "ru", "nl", "cs", "ar", "zh-cn", "ja", "hu", "ko", "hi"
            ],
            accepts_text_prompt=True,
        )

    async def load(self) -> None:
        """Load the XTTS model."""
        if self._loaded:
            return

        try:
            from TTS.api import TTS as CoquiTTS
            import torch

            device = "cuda" if torch.cuda.is_available() else "cpu"
            model_name = self.config.custom.get("model_name", "tts_models/multilingual/multi-dataset/xtts_v2")
            
            print(f"[CoquiXTTS] Loading model: {model_name}")
            self._tts = CoquiTTS(model_name=model_name, progress_bar=False).to(device)
            self._loaded = True
            print("[CoquiXTTS] Model loaded successfully")
            
        except ImportError:
            raise RuntimeError("Coqui TTS not installed. Install with: pip install TTS")
        except Exception as e:
            raise RuntimeError(f"Failed to load XTTS model: {e}")

    async def unload(self) -> None:
        """Unload the model and free VRAM."""
        if self._tts is not None:
            try:
                import torch
                import gc
                
                del self._tts
                self._tts = None
                gc.collect()
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
                    
            except Exception as e:
                print(f"[CoquiXTTS] Error unloading: {e}")
        
        self._loaded = False

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
        """Generate speech from text."""
        if not self._loaded:
            await self.load()

        if progress_callback:
            await progress_callback(JobProgressEvent(
                job_id="",
                seq=0,
                stage="generating_audio",
                stage_progress=0.1,
                overall_progress=0.1,
                message=f"Generating audio for: {text[:50]}...",
            ))

        try:
            # Ensure output directory exists
            os.makedirs(os.path.dirname(output_path), exist_ok=True)

            # Build TTS arguments
            tts_kwargs = {
                "language": language,
                "file_path": output_path,
            }
            
            # Add voice sample for cloning if provided
            if voice_sample_path and os.path.exists(voice_sample_path):
                tts_kwargs["speaker_wav"] = voice_sample_path
            
            # Generate audio
            self._tts.tts_to_file(text, **tts_kwargs)

            if progress_callback:
                await progress_callback(JobProgressEvent(
                    job_id="",
                    seq=0,
                    stage="measuring_duration",
                    stage_progress=0.8,
                    overall_progress=0.8,
                    message="Measuring audio duration...",
                ))

            # Get duration
            duration = 0.0
            try:
                from moviepy import AudioFileClip
                
                if os.path.exists(output_path) and os.path.getsize(output_path) > 0:
                    with AudioFileClip(output_path) as audio_clip:
                        duration = audio_clip.duration + 0.1  # Small buffer
                else:
                    raise ValueError("Audio file not generated or is empty")
                    
            except Exception as e:
                print(f"[CoquiXTTS] Error getting duration: {e}")
                # Create fallback silent audio
                import numpy as np
                from scipy.io import wavfile
                
                samplerate = 22050
                wavfile.write(output_path, samplerate, np.zeros(int(0.1 * samplerate), dtype=np.int16))
                duration = 0.1

            if progress_callback:
                await progress_callback(JobProgressEvent(
                    job_id="",
                    seq=0,
                    stage="completed",
                    stage_progress=1.0,
                    overall_progress=1.0,
                    message="Audio generation complete",
                ))

            return TTSResult(
                success=True,
                artifact_path=output_path,
                text=text,
                duration_seconds=duration,
                sample_rate=22050,
            )

        except Exception as e:
            return TTSResult(
                success=False,
                error=str(e),
                text=text,
            )
