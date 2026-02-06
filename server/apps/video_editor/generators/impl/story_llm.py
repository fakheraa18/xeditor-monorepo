"""
Story LLM Generator

Generates structured video stories using LLM providers.
Bridges the CodeEditor provider system for VideoEditor use.
"""

import json
from typing import Optional, Dict, Any, List

from apps.video_editor.generators.base import (
    LLMGenerator,
    LLMResult,
    ProgressCallback,
    JobProgressEvent,
)
from apps.video_editor.models import GeneratorCapabilities, GeneratorConfig, GeneratorType


# Default system prompt for story generation
STORY_SYSTEM_PROMPT = """You are a professional video script writer. Generate structured video scripts in JSON format.

Your output must be valid JSON with this exact structure:
{
  "title": "Story Title",
  "genre": "documentary|advertising|movie|music_video|educational|other",
  "synopsis": "Brief synopsis of the story",
  "main_subject_description": "Description of the main character/subject",
  "setting_description": "Description of the overall setting",
  "scenes": [
    {
      "title": "Scene 1 Title",
      "order": 0,
      "narration": "The narration text that will be spoken",
      "visual_prompt": "Detailed visual description for video generation",
      "camera_notes": "Camera angle and movement suggestions",
      "duration_estimate": 5.0
    }
  ]
}

Guidelines:
- Each scene narration should be concise (1-3 sentences, ~10-20 seconds when spoken)
- Visual prompts should be detailed and descriptive for AI video generation
- Include camera notes for cinematic direction
- Estimate realistic durations based on narration length
- Create 3-8 scenes for a complete story
"""


class StoryLLMGenerator(LLMGenerator):
    """
    LLM-based story generator that bridges the CodeEditor provider system.
    
    Features:
    - Uses any configured LLM provider (OpenAI, Anthropic, Ollama, etc.)
    - Generates structured JSON story output
    - Streaming support
    """

    def __init__(self, config: Optional[GeneratorConfig] = None):
        super().__init__(config)
        self._provider = None

    @classmethod
    def get_id(cls) -> str:
        return "story_llm"

    @classmethod
    def get_capabilities(cls) -> GeneratorCapabilities:
        return GeneratorCapabilities(
            id="story_llm",
            title="Story Generator (LLM)",
            description="Generate structured video stories using any LLM provider.",
            version="1.0.0",
            generator_type=GeneratorType.LLM,
            vram_gb_min=0.0,  # Uses API or separate process
            vram_gb_recommended=0.0,
            ram_gb_min=1.0,
            accepts_text_prompt=True,
            supports_streaming=True,
            max_context_tokens=128000,  # Varies by provider
        )

    async def load(self) -> None:
        """Load is a no-op for LLM - connection happens on demand."""
        self._loaded = True

    async def unload(self) -> None:
        """Unload is a no-op for LLM."""
        self._provider = None
        self._loaded = False

    def _get_provider_config(self) -> Dict[str, Any]:
        """Build provider config from generator config."""
        # Use custom config if provided, otherwise use defaults
        return {
            "provider": self.config.custom.get("provider", "openai"),
            "id": self.config.custom.get("model_id", "gpt-4"),
            "connection": self.config.custom.get("connection", {
                "baseUrl": "https://api.openai.com",
                "path": "/v1/chat/completions",
            }),
            "auth": self.config.custom.get("auth", {
                "type": "bearer",
                "apiKey": self.config.api_key or "",
            }),
            "family": self.config.custom.get("family", "gpt"),
        }

    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        max_tokens: int = 4096,
        temperature: float = 0.7,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> LLMResult:
        """Generate story using LLM."""
        
        if progress_callback:
            await progress_callback(JobProgressEvent(
                job_id="",
                seq=0,
                stage="connecting",
                stage_progress=0.1,
                overall_progress=0.1,
                message="Connecting to LLM provider...",
            ))

        try:
            from apps.code_editor.providers import get_provider, LLMRequest

            provider_config = self._get_provider_config()
            provider = get_provider(provider_config)

            # Use story system prompt if none provided
            sys_prompt = system_prompt or STORY_SYSTEM_PROMPT

            # Build request
            request = LLMRequest(
                model_id=provider_config.get("id", "gpt-4"),
                messages=[
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": prompt},
                ],
                temperature=temperature,
                max_tokens=max_tokens,
                provider=provider_config.get("provider", ""),
                connection=provider_config.get("connection", {}),
                auth=provider_config.get("auth", {}),
                family=provider_config.get("family"),
            )

            if progress_callback:
                await progress_callback(JobProgressEvent(
                    job_id="",
                    seq=0,
                    stage="generating",
                    stage_progress=0.3,
                    overall_progress=0.3,
                    message="Generating story...",
                ))

            # Use non-streaming chat for simplicity
            response = await provider.chat(request)

            if response.error:
                return LLMResult(
                    success=False,
                    error=response.error,
                )

            if progress_callback:
                await progress_callback(JobProgressEvent(
                    job_id="",
                    seq=0,
                    stage="completed",
                    stage_progress=1.0,
                    overall_progress=1.0,
                    message="Story generation complete",
                ))

            return LLMResult(
                success=True,
                content=response.content,
                finish_reason=response.finish_reason,
                usage=response.usage,
            )

        except ImportError as e:
            return LLMResult(
                success=False,
                error=f"CodeEditor providers not available: {e}",
            )
        except Exception as e:
            return LLMResult(
                success=False,
                error=str(e),
            )

    def parse_story_response(self, content: str) -> Optional[Dict[str, Any]]:
        """Parse the LLM response into a structured story dict."""
        try:
            # Try to extract JSON from the response
            # Handle cases where JSON is wrapped in markdown code blocks
            content = content.strip()
            
            if content.startswith("```json"):
                content = content[7:]
            elif content.startswith("```"):
                content = content[3:]
            
            if content.endswith("```"):
                content = content[:-3]
            
            content = content.strip()
            
            return json.loads(content)
            
        except json.JSONDecodeError as e:
            print(f"[StoryLLM] Failed to parse JSON: {e}")
            return None

    async def generate_story(
        self,
        topic: str,
        genre: Optional[str] = None,
        num_scenes: int = 5,
        additional_instructions: Optional[str] = None,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> Dict[str, Any]:
        """
        High-level story generation with topic input.
        
        Returns:
            Dict with story structure or error info
        """
        # Build the user prompt
        prompt_parts = [f"Create a {genre or 'video'} script about: {topic}"]
        prompt_parts.append(f"Generate approximately {num_scenes} scenes.")
        
        if additional_instructions:
            prompt_parts.append(f"Additional requirements: {additional_instructions}")
        
        prompt_parts.append("Output valid JSON only, no explanations.")
        
        prompt = "\n".join(prompt_parts)

        result = await self.generate(
            prompt=prompt,
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
