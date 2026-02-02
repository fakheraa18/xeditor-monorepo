"""
OpenAI provider using LiteLLM for OpenAI, Anthropic, and Ollama.

This provider handles the standard OpenAI-compatible API and leverages
LiteLLM for multi-provider support.
"""

import os
from typing import AsyncGenerator, Dict, Any

import litellm

from .base import LLMProvider
from .events import LLMEvent, LLMRequest, TokenUsage


class OpenAIProvider(LLMProvider):
    """
    Provider for OpenAI and Anthropic using LiteLLM.
    
    LiteLLM abstracts away the differences between these providers,
    allowing us to use a unified interface.
    
    Note: Ollama is now handled by OllamaProvider for better control and debugging.
    """
    
    # Providers that LiteLLM handles
    SUPPORTED_PROVIDERS = {"openai", "anthropic"}
    
    async def stream(self, request: LLMRequest) -> AsyncGenerator[LLMEvent, None]:
        """Stream response using LiteLLM."""
        provider = request.provider or self.config.get("provider", "")
        
        if provider not in self.SUPPORTED_PROVIDERS:
            yield LLMEvent(
                type="error",
                error=f"OpenAIProvider does not support provider: {provider}"
            )
            return
        
        # Construct litellm model string
        litellm_model = f"{provider}/{request.model_id}"
        
        # Configure API key via litellm's built-in config (not os.environ)
        # This is per-request and thread-safe
        api_key = None
        if self.auth.get("type") == "bearer" and self.auth.get("apiKey"):
            api_key = self.auth["apiKey"]
        
        # Build kwargs
        litellm_kwargs: Dict[str, Any] = {
            "model": litellm_model,
            "messages": request.messages,
            "temperature": request.temperature,
            "stream": True,
        }
        
        if request.max_tokens:
            litellm_kwargs["max_tokens"] = request.max_tokens
        
        # Merge extra payload
        if request.extra_payload:
            litellm_kwargs.update(request.extra_payload)
        
        # Set API key in kwargs (litellm supports this)
        if api_key:
            litellm_kwargs["api_key"] = api_key
        
        try:
            full_content = ""
            finish_reason = None
            usage = None
            
            response = await litellm.acompletion(**litellm_kwargs)
            
            async for chunk in response:
                if hasattr(chunk, 'choices') and len(chunk.choices) > 0:
                    delta = chunk.choices[0].delta
                    
                    if hasattr(delta, 'content') and delta.content:
                        full_content += delta.content
                        yield LLMEvent(type="content", content=delta.content)
                    
                    if hasattr(chunk.choices[0], 'finish_reason') and chunk.choices[0].finish_reason:
                        finish_reason = chunk.choices[0].finish_reason
                
                if hasattr(chunk, 'usage') and chunk.usage:
                    # Normalize usage using TokenUsage dataclass
                    token_usage = TokenUsage(
                        prompt_tokens=chunk.usage.prompt_tokens or 0,
                        completion_tokens=chunk.usage.completion_tokens or 0,
                        total_tokens=chunk.usage.total_tokens or 0,
                    )
                    usage = token_usage.to_dict()
            
            yield LLMEvent(
                type="end",
                usage=usage,
                finish_reason=finish_reason,
            )
            
        except Exception as e:
            error_str = str(e)
            error_lower = error_str.lower()
            
            # Check if it's an authentication error
            is_auth_error = (
                "api_key" in error_lower or 
                "api key" in error_lower or
                "authentication" in error_lower or
                "unauthorized" in error_lower or
                "invalid api" in error_lower
            )
            
            if is_auth_error and provider in ["openai", "anthropic"]:
                api_key_provided = self.auth.get("type") == "bearer" and self.auth.get("apiKey")
                
                if not api_key_provided:
                    error_message = f"API key is required for {provider.upper()} models. Please configure your API key in the model settings."
                else:
                    error_message = f"Authentication failed for {provider.upper()}. Please check your API key: {error_str}"
                
                yield LLMEvent(type="error", error=error_message)
            else:
                yield LLMEvent(type="error", error=f"LiteLLM error: {error_str}")
