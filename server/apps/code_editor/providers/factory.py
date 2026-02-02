"""
Provider factory for selecting the appropriate LLM provider.

Routes requests to the correct provider based on configuration.
"""

from typing import Dict, Any

from .base import LLMProvider
from .openai import OpenAIProvider
from .gemini import GeminiProvider, is_gemini_endpoint
from .kimi import KimiProvider, is_kimi_endpoint
from .lmstudio import LMStudioProvider
from .vllm import VLLMProvider
from .ollama import OllamaProvider
from .http import GenericHTTPProvider


def get_provider(config: Dict[str, Any]) -> LLMProvider:
    """
    Get the appropriate LLM provider for the given configuration.
    
    Selection logic:
    1. Check explicit provider ID (vllm, lmstudio, local_companion)
    2. Check base URL for provider-specific patterns (Gemini, Kimi)
    3. Check for LiteLLM-supported providers (openai, anthropic, ollama)
    4. Fallback to generic OpenAI-compatible HTTP provider
    
    Args:
        config: Model configuration including provider, connection, auth, etc.
        
    Returns:
        LLMProvider instance for the configuration
    """
    provider_id = config.get("provider", "")
    connection = config.get("connection", {})
    base_url = connection.get("baseUrl", "")
    path = connection.get("path", "")
    
    # Extract auth from connection if present
    if "auth" not in config and "auth" in connection:
        config["auth"] = connection["auth"]
    
    # 1. Check by explicit provider ID
    if provider_id == "vllm":
        return VLLMProvider(config)
    
    if provider_id == "local_companion":
        # local_companion now only supports vllm
        runner = config.get("localCompanion", {}).get("runner", "vllm")
        if runner == "vllm":
            return VLLMProvider(config)
        # Fallback for other runners (error will be raised by provider)
        return VLLMProvider(config)
    
    if provider_id == "lmstudio":
        return LMStudioProvider(config)
    
    # 2. Check by base URL patterns
    if is_gemini_endpoint(base_url, path):
        return GeminiProvider(config)
    
    if is_kimi_endpoint(base_url, path):
        return KimiProvider(config)
    
    # 3. Check for Ollama provider
    if provider_id == "ollama":
        return OllamaProvider(config)
    
    # 4. Check for LiteLLM-supported providers (OpenAI, Anthropic)
    if provider_id in OpenAIProvider.SUPPORTED_PROVIDERS:
        return OpenAIProvider(config)
    
    # 5. Fallback: generic OpenAI-compatible HTTP
    return GenericHTTPProvider(config)


def get_provider_for_request(request_payload: Dict[str, Any]) -> LLMProvider:
    """
    Get provider from a request payload (as sent from apps.code_editor.agent_runner).
    
    This is a convenience function that builds the config from the request payload.
    
    Args:
        request_payload: Request payload with provider, modelId, connection, auth, etc.
        
    Returns:
        LLMProvider instance
    """
    config = {
        "provider": request_payload.get("provider", ""),
        "id": request_payload.get("modelId", ""),
        "connection": request_payload.get("connection", {}),
        "auth": request_payload.get("auth", {}),
        "localCompanion": {"runner": request_payload.get("runner", "vllm")},
        "family": request_payload.get("family"),
        "version": request_payload.get("version"),
    }
    
    return get_provider(config)
