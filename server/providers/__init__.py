"""
LLM Provider package.

Provides a unified interface for different LLM providers (OpenAI, Gemini, LM Studio, vLLM, etc.)
through the Provider Adapter pattern. Each provider normalizes its responses into structured
LLMEvents that the rest of the system can consume uniformly.
"""

from .events import LLMEvent, LLMResponse, LLMRequest
from .base import LLMProvider
from .factory import get_provider, get_provider_for_request

# Provider implementations
from .openai import OpenAIProvider
from .gemini import GeminiProvider, is_gemini_endpoint
from .lmstudio import LMStudioProvider
from .vllm import VLLMProvider
from .ollama import OllamaProvider
from .http import GenericHTTPProvider

__all__ = [
    # Events
    "LLMEvent",
    "LLMResponse",
    "LLMRequest",
    # Base
    "LLMProvider",
    # Factory
    "get_provider",
    "get_provider_for_request",
    # Providers
    "OpenAIProvider",
    "GeminiProvider",
    "is_gemini_endpoint",
    "LMStudioProvider",
    "VLLMProvider",
    "OllamaProvider",
    "GenericHTTPProvider",
]
