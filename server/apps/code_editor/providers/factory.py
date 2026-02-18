"""
Provider factory for selecting the appropriate LLM provider.

All requests are routed through LiteLLMProvider for unified execution.
"""

from typing import Dict, Any

from .base import LLMProvider
from .litellm_provider import LiteLLMProvider


def get_provider(config: Dict[str, Any]) -> LLMProvider:
    """
    Get the LiteLLM provider for the given configuration.

    All providers (openai, anthropic, ollama, lmstudio, vllm, openai_compatible,
    local_companion, etc.) are routed through LiteLLM with runtime model prefix
    normalization.

    Args:
        config: Model configuration including provider, connection, auth, etc.

    Returns:
        LiteLLMProvider instance
    """
    if "auth" not in config and "auth" in config.get("connection", {}):
        config["auth"] = config["connection"]["auth"]

    return LiteLLMProvider(config)


def get_provider_for_request(request_payload: Dict[str, Any]) -> LLMProvider:
    """
    Get provider from a request payload (as sent from agent_runner).

    Args:
        request_payload: Request payload with provider, modelId, connection, auth, etc.

    Returns:
        LiteLLMProvider instance
    """
    connection = request_payload.get("connection", {})
    config = {
        "provider": request_payload.get("provider", ""),
        "id": request_payload.get("modelId", ""),
        "connection": connection,
        "auth": request_payload.get("auth") or connection.get("auth", {}),
        "localCompanion": request_payload.get("localCompanion") or {"runner": request_payload.get("runner", "vllm")},
        "family": request_payload.get("family"),
        "version": request_payload.get("version"),
    }
    return get_provider(config)
