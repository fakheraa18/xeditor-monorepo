"""
LLM Provider package.

All requests are routed through LiteLLMProvider for unified execution
across OpenAI, Anthropic, Ollama, LM Studio, vLLM, OpenAI-compatible endpoints, etc.
"""

from .events import LLMEvent, LLMResponse, LLMRequest, TokenUsage
from .base import LLMProvider
from .factory import get_provider, get_provider_for_request
from .litellm_provider import LiteLLMProvider
from .normalize import normalize_model_name, PROVIDER_TO_PREFIX

__all__ = [
    "LLMEvent",
    "LLMResponse",
    "LLMRequest",
    "TokenUsage",
    "LLMProvider",
    "get_provider",
    "get_provider_for_request",
    "LiteLLMProvider",
    "normalize_model_name",
    "PROVIDER_TO_PREFIX",
]
