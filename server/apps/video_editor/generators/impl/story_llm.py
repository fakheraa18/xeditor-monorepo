"""
Story LLM Generator

Generates structured video stories using either:
  1. Local Transformers models (downloaded from HuggingFace)
  2. Remote/local API providers (Ollama, LM Studio, OpenAI, Anthropic, etc.)

No hardcoded provider defaults -- the user must choose a backend.
"""

import json
import re
from pathlib import Path
from typing import Optional, Dict, Any, List

from apps.video_editor.generators.base import (
    LLMGenerator,
    LLMResult,
    ProgressCallback,
    JobProgressEvent,
)
from apps.video_editor.models import (
    GeneratorCapabilities,
    GeneratorConfig,
    GeneratorType,
    GeneratorUiSchema,
    UiSection,
    UiField,
    UiFieldType,
    UiFieldOption,
    UiFieldConstraints,
    ModelInstallable,
)


# ─────────────────────────────────────────────────────────────────────────────
# Default cache directory for downloaded models
# ─────────────────────────────────────────────────────────────────────────────

DEFAULT_MODELS_CACHE = str(Path.home() / ".cache" / "xeditor" / "models" / "hf")


# ─────────────────────────────────────────────────────────────────────────────
# Curated model presets (local Transformers)
# ─────────────────────────────────────────────────────────────────────────────

LOCAL_MODEL_PRESETS: List[Dict[str, Any]] = [
    {
        "id": "Qwen/Qwen2.5-3B-Instruct",
        "label": "Qwen 2.5 3B Instruct (small, fast)",
        "size_gb": 6.5,
        "license": "Apache-2.0",
    },
    {
        "id": "Qwen/Qwen2.5-7B-Instruct",
        "label": "Qwen 2.5 7B Instruct (balanced)",
        "size_gb": 15.0,
        "license": "Apache-2.0",
    },
    {
        "id": "mistralai/Mistral-7B-Instruct-v0.3",
        "label": "Mistral 7B Instruct v0.3",
        "size_gb": 14.5,
        "license": "Apache-2.0",
    },
    {
        "id": "meta-llama/Llama-3.1-8B-Instruct",
        "label": "Llama 3.1 8B Instruct",
        "size_gb": 16.0,
        "license": "Llama 3.1 Community",
    },
    {
        "id": "google/gemma-2-2b-it",
        "label": "Gemma 2 2B IT (tiny, fast)",
        "size_gb": 5.0,
        "license": "Gemma",
    },
]


# ─────────────────────────────────────────────────────────────────────────────
# System prompt for script generation
# ─────────────────────────────────────────────────────────────────────────────

def build_story_system_prompt(
    characters: Optional[List[Dict[str, str]]] = None,
) -> str:
    """Build the system prompt, optionally injecting known characters."""
    char_block = ""
    if characters:
        lines = []
        for ch in characters:
            lines.append(
                f'  - code="{ch["code"]}", name="{ch["name"]}"'
                + (f', description="{ch["description"]}"' if ch.get("description") else "")
            )
        char_block = (
            "\n\nAvailable characters (use their code as \"speaker\"):\n"
            + "\n".join(lines)
            + '\nFor narration lines, use speaker="NARRATOR".'
        )

    return f"""You are a professional video script writer. Generate structured video scripts in JSON format.

Your output MUST be valid JSON with this exact structure:
{{
  "title": "Story Title",
  "genre": "documentary|advertising|movie|music_video|educational|other",
  "synopsis": "Brief synopsis of the story",
  "main_subject_description": "Description of the main character/subject",
  "setting_description": "Description of the overall setting",
  "scenes": [
    {{
      "title": "Scene 1 Title",
      "order": 0,
      "visual_prompt": "Detailed visual description for video generation",
      "camera_notes": "Camera angle and movement suggestions",
      "duration_estimate": 8.0,
      "script_lines": [
        {{
          "speaker": "NARRATOR",
          "text": "Narration text that will be spoken",
          "emotion_hint": "calm",
          "duration_hint": 5.0
        }},
        {{
          "speaker": "CHARACTER_CODE",
          "text": "Character dialogue line",
          "emotion_hint": "excited",
          "duration_hint": 3.0
        }}
      ]
    }}
  ]
}}

Guidelines:
- Each scene should have one or more script_lines with speaker, text, and optional emotion/duration hints
- speaker is "NARRATOR" for narration or a character code for dialogue
- Emotion hints: calm, happy, sad, angry, excited, whisper, dramatic, neutral
- Visual prompts should be detailed and descriptive for AI video generation
- Include camera notes for cinematic direction
- duration_estimate per scene should match the sum of script_line durations
- Keep dialogue natural and concise
- Output valid JSON ONLY, no explanations or markdown{char_block}"""


# ─────────────────────────────────────────────────────────────────────────────
# UI schema for the generator settings panel
# ─────────────────────────────────────────────────────────────────────────────

def _build_ui_schema() -> GeneratorUiSchema:
    """Build the UI schema for StoryLLM generator settings."""
    model_options = [
        UiFieldOption(value=p["id"], label=p["label"])
        for p in LOCAL_MODEL_PRESETS
    ]

    return GeneratorUiSchema(sections=[
        UiSection(
            key="backend",
            label="LLM Backend",
            description="Choose how to run the text model",
            fields=[
                UiField(
                    key="backend",
                    label="Backend",
                    field_type=UiFieldType.SELECT,
                    default="local",
                    required=True,
                    options=[
                        UiFieldOption(value="local", label="Local (Transformers)"),
                        UiFieldOption(value="provider", label="API Provider (Ollama / LM Studio / OpenAI / …)"),
                    ],
                    description="Local downloads and runs the model on your GPU. Provider calls an API.",
                ),
            ],
        ),
        UiSection(
            key="local_settings",
            label="Local Model Settings",
            description="Settings for local Transformers inference",
            fields=[
                UiField(
                    key="model_repo_id",
                    label="HuggingFace Model",
                    field_type=UiFieldType.SELECT,
                    default="Qwen/Qwen2.5-3B-Instruct",
                    required=True,
                    options=model_options,
                    description="Select a model to download and run locally",
                    depends_on="backend",  # visible when backend is truthy; we'll handle logic in generate()
                ),
                UiField(
                    key="custom_model_repo_id",
                    label="Custom HF Repo ID",
                    field_type=UiFieldType.STRING,
                    description="Enter a custom HuggingFace repo ID (overrides the dropdown above)",
                    placeholder="org/model-name",
                ),
                UiField(
                    key="torch_dtype",
                    label="Precision",
                    field_type=UiFieldType.SELECT,
                    default="auto",
                    options=[
                        UiFieldOption(value="auto", label="Auto"),
                        UiFieldOption(value="float16", label="Float16 (less VRAM)"),
                        UiFieldOption(value="bfloat16", label="BFloat16"),
                        UiFieldOption(value="float32", label="Float32 (more VRAM)"),
                    ],
                ),
            ],
        ),
        UiSection(
            key="provider_settings",
            label="API Provider Settings",
            description="Settings for remote or local API inference",
            fields=[
                UiField(
                    key="provider_type",
                    label="Provider",
                    field_type=UiFieldType.SELECT,
                    default="ollama",
                    options=[
                        UiFieldOption(value="ollama", label="Ollama"),
                        UiFieldOption(value="lmstudio", label="LM Studio"),
                        UiFieldOption(value="openai", label="OpenAI"),
                        UiFieldOption(value="anthropic", label="Anthropic (Claude)"),
                        UiFieldOption(value="openai_compatible", label="OpenAI-Compatible"),
                    ],
                    depends_on="backend",
                ),
                UiField(
                    key="provider_base_url",
                    label="Base URL",
                    field_type=UiFieldType.STRING,
                    default="http://localhost:11434",
                    placeholder="http://localhost:11434",
                    description="API base URL",
                    depends_on="backend",
                ),
                UiField(
                    key="provider_model_id",
                    label="Model ID",
                    field_type=UiFieldType.STRING,
                    default="llama3.1",
                    placeholder="llama3.1 / gpt-4o / claude-3-5-sonnet …",
                    description="The model identifier for the provider",
                    depends_on="backend",
                ),
                UiField(
                    key="provider_api_key",
                    label="API Key",
                    field_type=UiFieldType.STRING,
                    placeholder="sk-... (leave blank for local providers)",
                    description="API key (optional for Ollama/LM Studio)",
                    depends_on="backend",
                ),
            ],
        ),
        UiSection(
            key="generation",
            label="Generation Parameters",
            default_collapsed=True,
            fields=[
                UiField(
                    key="temperature",
                    label="Temperature",
                    field_type=UiFieldType.FLOAT,
                    default=0.7,
                    constraints=UiFieldConstraints(min_value=0.0, max_value=2.0, step=0.05),
                ),
                UiField(
                    key="max_new_tokens",
                    label="Max New Tokens",
                    field_type=UiFieldType.INT,
                    default=4096,
                    constraints=UiFieldConstraints(min_value=256, max_value=16384, step=256),
                ),
                UiField(
                    key="top_p",
                    label="Top-P",
                    field_type=UiFieldType.FLOAT,
                    default=0.9,
                    constraints=UiFieldConstraints(min_value=0.0, max_value=1.0, step=0.05),
                ),
            ],
        ),
    ])


# ─────────────────────────────────────────────────────────────────────────────
# Installables (for model_download job)
# ─────────────────────────────────────────────────────────────────────────────

def _build_installables() -> List[ModelInstallable]:
    return [
        ModelInstallable(
            name=p["label"],
            url=f"https://huggingface.co/{p['id']}",
            size_gb=p.get("size_gb"),
            license=p.get("license"),
            variant=p["id"],  # use repo id as variant for identification
        )
        for p in LOCAL_MODEL_PRESETS
    ]


# ─────────────────────────────────────────────────────────────────────────────
# StoryLLMGenerator
# ─────────────────────────────────────────────────────────────────────────────

class StoryLLMGenerator(LLMGenerator):
    """
    LLM-based story generator with dual backend support.

    Backends:
      - 'local': Downloads + runs a HuggingFace model via Transformers on local GPU/CPU
      - 'provider': Calls any OpenAI-compatible API (Ollama, LM Studio, OpenAI, Anthropic …)
    """

    def __init__(self, config: Optional[GeneratorConfig] = None):
        super().__init__(config)
        self._model = None
        self._tokenizer = None

    @classmethod
    def get_id(cls) -> str:
        return "story_llm"

    @classmethod
    def get_capabilities(cls) -> GeneratorCapabilities:
        return GeneratorCapabilities(
            id="story_llm",
            title="Story Generator (LLM)",
            description="Generate structured video scripts using a local model or API provider.",
            version="2.0.0",
            generator_type=GeneratorType.LLM,
            vram_gb_min=0.0,
            vram_gb_recommended=6.0,
            ram_gb_min=4.0,
            accepts_text_prompt=True,
            supports_streaming=True,
            max_context_tokens=128000,
            ui_schema=_build_ui_schema(),
            installables=_build_installables(),
        )

    # ── helpers ──────────────────────────────────────────────────────────

    def _get_backend(self) -> str:
        return self.config.custom.get("backend", "local")

    def _get_local_model_id(self) -> str:
        custom = self.config.custom.get("custom_model_repo_id", "")
        if custom and custom.strip():
            return custom.strip()
        return self.config.custom.get("model_repo_id", "Qwen/Qwen2.5-3B-Instruct")

    def _get_models_cache_dir(self) -> str:
        return self.config.custom.get("models_cache_dir", DEFAULT_MODELS_CACHE)

    # ── load / unload (only matters for local backend) ───────────────────

    async def load(self) -> None:
        """Load model (local backend only)."""
        if self._loaded:
            return

        if self._get_backend() == "local":
            await self._load_local_model()
        else:
            # Provider mode: nothing to pre-load
            pass

        self._loaded = True

    async def _load_local_model(self) -> None:
        """Load a HuggingFace Transformers model for local inference."""
        try:
            import torch
            from transformers import AutoTokenizer, AutoModelForCausalLM
        except ImportError as exc:
            raise RuntimeError(
                "transformers + torch required for local inference. "
                "Install with: uv pip install 'local-companion[video_editor]'"
            ) from exc

        model_id = self._get_local_model_id()
        cache_dir = self._get_models_cache_dir()

        dtype_str = self.config.custom.get("torch_dtype", "auto")
        if dtype_str == "float16":
            dtype = torch.float16
        elif dtype_str == "bfloat16":
            dtype = torch.bfloat16
        elif dtype_str == "float32":
            dtype = torch.float32
        else:
            dtype = "auto"  # type: ignore[assignment]

        print(f"[StoryLLM] Loading local model: {model_id} (dtype={dtype_str})")

        self._tokenizer = AutoTokenizer.from_pretrained(
            model_id, cache_dir=cache_dir, trust_remote_code=True,
        )
        self._model = AutoModelForCausalLM.from_pretrained(
            model_id,
            cache_dir=cache_dir,
            torch_dtype=dtype,
            device_map="auto",
            trust_remote_code=True,
        )
        print(f"[StoryLLM] Model loaded: {model_id}")

    async def unload(self) -> None:
        """Unload model and free VRAM."""
        if self._model is not None:
            try:
                import torch
                import gc

                del self._model
                del self._tokenizer
                self._model = None
                self._tokenizer = None

                gc.collect()
                if torch.cuda.is_available():
                    torch.cuda.empty_cache()
            except Exception as exc:
                print(f"[StoryLLM] Error unloading model: {exc}")

        self._loaded = False

    # ── core generate ────────────────────────────────────────────────────

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> LLMResult:
        """Generate text using the selected backend."""
        backend = self._get_backend()

        if progress_callback:
            await progress_callback(JobProgressEvent(
                job_id="",
                seq=0,
                stage="connecting",
                stage_progress=0.1,
                overall_progress=0.1,
                message=f"Starting {backend} LLM inference…",
            ))

        try:
            if backend == "local":
                return await self._generate_local(prompt, system_prompt, max_tokens, temperature, progress_callback)
            else:
                return await self._generate_provider(prompt, system_prompt, max_tokens, temperature, progress_callback)
        except Exception as exc:
            return LLMResult(success=False, error=str(exc))

    # ── local Transformers inference ─────────────────────────────────────

    async def _generate_local(
        self,
        prompt: str,
        system_prompt: Optional[str],
        max_tokens: int,
        temperature: float,
        progress_callback: Optional[ProgressCallback],
    ) -> LLMResult:
        if self._model is None or self._tokenizer is None:
            await self._load_local_model()

        import torch

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        # Use the chat template if available
        if hasattr(self._tokenizer, "apply_chat_template"):
            text = self._tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True,
            )
        else:
            # Fallback: concatenate
            text = "\n".join(m["content"] for m in messages)

        inputs = self._tokenizer(text, return_tensors="pt").to(self._model.device)

        if progress_callback:
            await progress_callback(JobProgressEvent(
                job_id="", seq=0, stage="generating",
                stage_progress=0.3, overall_progress=0.3,
                message="Generating story (local model)…",
            ))

        top_p = self.config.custom.get("top_p", 0.9)

        with torch.no_grad():
            output_ids = self._model.generate(
                **inputs,
                max_new_tokens=max_tokens,
                temperature=max(temperature, 0.01),
                top_p=top_p,
                do_sample=True,
            )

        # Decode only the new tokens
        new_token_ids = output_ids[0][inputs["input_ids"].shape[1]:]
        content = self._tokenizer.decode(new_token_ids, skip_special_tokens=True)

        if progress_callback:
            await progress_callback(JobProgressEvent(
                job_id="", seq=0, stage="completed",
                stage_progress=1.0, overall_progress=1.0,
                message="Story generation complete",
            ))

        return LLMResult(success=True, content=content)

    # ── API provider inference ───────────────────────────────────────────

    async def _generate_provider(
        self,
        prompt: str,
        system_prompt: Optional[str],
        max_tokens: int,
        temperature: float,
        progress_callback: Optional[ProgressCallback],
    ) -> LLMResult:
        """Generate using an OpenAI-compatible API (Ollama, LM Studio, OpenAI, Anthropic)."""
        import httpx

        provider_type = self.config.custom.get("provider_type", "ollama")
        base_url = self.config.custom.get("provider_base_url", "http://localhost:11434")
        model_id = self.config.custom.get("provider_model_id", "llama3.1")
        api_key = self.config.custom.get("provider_api_key", "")

        # Build chat completions URL
        base_url = base_url.rstrip("/")
        if provider_type == "ollama":
            url = f"{base_url}/v1/chat/completions"
        elif provider_type == "lmstudio":
            url = f"{base_url}/v1/chat/completions"
        elif provider_type == "anthropic":
            url = f"{base_url}/v1/messages"
        else:
            # openai, openai_compatible
            url = f"{base_url}/v1/chat/completions"

        messages: List[Dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        headers: Dict[str, str] = {"Content-Type": "application/json"}
        if api_key:
            if provider_type == "anthropic":
                headers["x-api-key"] = api_key
                headers["anthropic-version"] = "2023-06-01"
            else:
                headers["Authorization"] = f"Bearer {api_key}"

        if progress_callback:
            await progress_callback(JobProgressEvent(
                job_id="", seq=0, stage="generating",
                stage_progress=0.3, overall_progress=0.3,
                message=f"Calling {provider_type} ({model_id})…",
            ))

        # Anthropic uses a different request format
        if provider_type == "anthropic":
            body: Dict[str, Any] = {
                "model": model_id,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": messages,
            }
            if system_prompt:
                body["system"] = system_prompt
                body["messages"] = [m for m in messages if m["role"] != "system"]
        else:
            body = {
                "model": model_id,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens,
            }

        async with httpx.AsyncClient(timeout=300.0) as client:
            resp = await client.post(url, json=body, headers=headers)

        if resp.status_code != 200:
            return LLMResult(
                success=False,
                error=f"Provider returned {resp.status_code}: {resp.text[:500]}",
            )

        data = resp.json()

        # Parse response (OpenAI vs Anthropic format)
        if provider_type == "anthropic":
            content = ""
            for block in data.get("content", []):
                if block.get("type") == "text":
                    content += block.get("text", "")
        else:
            choices = data.get("choices", [])
            if not choices:
                return LLMResult(success=False, error="No choices in provider response")
            content = choices[0].get("message", {}).get("content", "")

        if progress_callback:
            await progress_callback(JobProgressEvent(
                job_id="", seq=0, stage="completed",
                stage_progress=1.0, overall_progress=1.0,
                message="Story generation complete",
            ))

        return LLMResult(
            success=True,
            content=content,
            usage=data.get("usage"),
        )

    # ── JSON parser ──────────────────────────────────────────────────────

    @staticmethod
    def parse_story_response(content: str) -> Optional[Dict[str, Any]]:
        """
        Parse the LLM response into a structured story dict.
        Handles markdown code blocks, extra text before/after JSON, etc.
        """
        content = content.strip()

        # Strip markdown code fences
        if "```json" in content:
            content = content.split("```json", 1)[1]
        elif "```" in content:
            content = content.split("```", 1)[1]
        if content.rstrip().endswith("```"):
            content = content.rsplit("```", 1)[0]
        content = content.strip()

        # Try direct parse first
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        # Try to find JSON object boundaries
        match = re.search(r'\{[\s\S]*\}', content)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        print(f"[StoryLLM] Failed to parse JSON from response ({len(content)} chars)")
        return None

    # ── high-level story generation ──────────────────────────────────────

    async def generate_story(
        self,
        topic: str,
        genre: Optional[str] = None,
        num_scenes: int = 5,
        target_duration_seconds: Optional[float] = None,
        characters: Optional[List[Dict[str, str]]] = None,
        additional_instructions: Optional[str] = None,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> Dict[str, Any]:
        """
        High-level story generation.

        Returns dict with 'story' key on success, or 'error' on failure.
        """
        # Build user prompt
        prompt_parts = [f"Create a {genre or 'video'} script about: {topic}"]
        prompt_parts.append(f"Generate approximately {num_scenes} scenes.")

        if target_duration_seconds:
            minutes = target_duration_seconds / 60
            prompt_parts.append(
                f"The total video should be approximately {target_duration_seconds:.0f} seconds "
                f"(~{minutes:.1f} minutes). Distribute scene durations accordingly."
            )

        prompt_parts.append(
            "Include both narration and character dialogue where appropriate. "
            "Each scene must have at least one script_line entry."
        )

        if additional_instructions:
            prompt_parts.append(f"Additional requirements: {additional_instructions}")

        prompt_parts.append("Output valid JSON only, no explanations or markdown.")

        prompt = "\n".join(prompt_parts)
        system_prompt = build_story_system_prompt(characters=characters)

        # Read temperature / max_tokens from config
        temperature = self.config.custom.get("temperature", 0.7)
        max_tokens = self.config.custom.get("max_new_tokens", 4096)

        result = await self.generate(
            prompt=prompt,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            temperature=temperature,
            progress_callback=progress_callback,
        )

        if not result.success:
            return {"error": result.error, "success": False}

        story = self.parse_story_response(result.content)
        if story is None:
            return {
                "error": "Failed to parse story JSON from LLM response",
                "raw_content": result.content,
                "success": False,
            }

        return {"story": story, "success": True}
