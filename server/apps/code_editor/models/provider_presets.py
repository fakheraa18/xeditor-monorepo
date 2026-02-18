"""
Provider Presets Registry for XEditor Local Companion.

LiteLLM-prefix catalog: provider IDs map 1:1 to LiteLLM route prefixes where possible.
Auth presets are simplified and prefix-based. No endpoint sniffing.
"""

from typing import Dict, Any, List, Optional


# ─────────────────────────────────────────────────────────────────────────────
# LiteLLM Provider Catalog - Source of truth for UI dropdown
# Provider IDs align with providers/normalize.py PROVIDER_TO_PREFIX
# ─────────────────────────────────────────────────────────────────────────────

LITELLM_PROVIDER_CATALOG: List[Dict[str, Any]] = [
    {"id": "openai", "label": "OpenAI", "helpText": "GPT-4, GPT-4o, and other OpenAI models"},
    {"id": "anthropic", "label": "Anthropic", "helpText": "Claude models"},
    {"id": "google", "label": "Google (Gemini)", "helpText": "Gemini models via Google AI Studio"},
    {"id": "openrouter", "label": "OpenRouter", "helpText": "Access multiple models through one API"},
    {"id": "ollama", "label": "Ollama", "helpText": "Local models via Ollama"},
    {"id": "lmstudio", "label": "LM Studio", "helpText": "Local models via LM Studio"},
    {"id": "vllm", "label": "vLLM", "helpText": "Local or remote vLLM server"},
    {"id": "sglang", "label": "SGLang", "helpText": "Local or remote SGLang server"},
    {"id": "kimi", "label": "Kimi (Moonshot)", "helpText": "Moonshot AI models"},
    {"id": "openai_compatible", "label": "OpenAI Compatible", "helpText": "Any OpenAI-compatible API endpoint"},
    {"id": "local_companion", "label": "Local Companion", "helpText": "Built-in vLLM managed by XEditor"},
]

PROVIDER_REGISTRY: List[Dict[str, Any]] = [
    {"id": p["id"], "label": p["label"]} for p in LITELLM_PROVIDER_CATALOG
]


def list_providers() -> List[Dict[str, Any]]:
    """List all available LLM providers for UI dropdown."""
    return PROVIDER_REGISTRY.copy()


# ─────────────────────────────────────────────────────────────────────────────
# Parameter Schema Definitions
# ─────────────────────────────────────────────────────────────────────────────

LMSTUDIO_PARAMETER_SCHEMA: List[Dict[str, Any]] = [
    {
        "id": "reasoning.enabled",
        "label": "Enable Reasoning",
        "type": "boolean",
        "default": False,
        "helpText": "Enable extended thinking/reasoning mode (uses /v1/responses endpoint)"
    },
    {
        "id": "reasoning.effort",
        "label": "Reasoning Effort",
        "type": "select",
        "options": [
            {"value": "low", "label": "Low"},
            {"value": "medium", "label": "Medium"},
            {"value": "high", "label": "High"}
        ],
        "default": "medium",
        "helpText": "Controls how much effort the model puts into reasoning",
        "dependsOn": {"field": "reasoning.enabled", "value": True}
    }
]

LMSTUDIO_PARAMETER_DEFAULTS: Dict[str, Any] = {
    "reasoning": {"enabled": False, "effort": "medium"}
}

GEMINI_PARAMETER_SCHEMA: List[Dict[str, Any]] = [
    {
        "id": "thinking.enabled",
        "label": "Enable Thinking",
        "type": "boolean",
        "default": False,
        "helpText": "Enable thinking mode for Gemini 2.5+ models"
    },
    {
        "id": "thinking.thinkingLevel",
        "label": "Thinking Level",
        "type": "select",
        "options": [
            {"value": "minimal", "label": "Minimal (Flash only)"},
            {"value": "low", "label": "Low"},
            {"value": "medium", "label": "Medium (Flash only)"},
            {"value": "high", "label": "High"}
        ],
        "default": "low",
        "helpText": "Thinking level for Gemini models.",
        "dependsOn": {"field": "thinking.enabled", "value": True}
    }
]

GEMINI_PARAMETER_DEFAULTS: Dict[str, Any] = {
    "thinking": {"enabled": False, "thinkingLevel": "low"}
}

OLLAMA_PARAMETER_SCHEMA: List[Dict[str, Any]] = [
    {
        "id": "thinking.enabled",
        "label": "Enable Thinking",
        "type": "boolean",
        "default": False,
        "helpText": "Enable extended thinking mode (requires model support)"
    }
]

OLLAMA_PARAMETER_DEFAULTS: Dict[str, Any] = {
    "thinking": {"enabled": False}
}


def get_provider_parameter_schema(provider: str) -> Optional[List[Dict[str, Any]]]:
    """Get the parameter schema for a provider."""
    provider_lower = provider.lower()
    if provider_lower == "lmstudio":
        return LMSTUDIO_PARAMETER_SCHEMA
    if provider_lower == "google":
        return GEMINI_PARAMETER_SCHEMA
    if provider_lower == "ollama":
        return OLLAMA_PARAMETER_SCHEMA
    return None


def get_provider_parameter_defaults(provider: str) -> Optional[Dict[str, Any]]:
    """Get the parameter defaults for a provider."""
    provider_lower = provider.lower()
    if provider_lower == "lmstudio":
        return LMSTUDIO_PARAMETER_DEFAULTS.copy()
    if provider_lower == "google":
        return GEMINI_PARAMETER_DEFAULTS.copy()
    if provider_lower == "ollama":
        return OLLAMA_PARAMETER_DEFAULTS.copy()
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Auth Presets (prefix-based, no endpoint sniffing)
# ─────────────────────────────────────────────────────────────────────────────

def get_provider_preset(
    provider: str,
    base_url: Optional[str] = None,
    family: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Get provider preset configuration for a given provider.
    Prefix-based: no endpoint sniffing. base_url is ignored for preset selection.
    """
    provider_lower = (provider or "").strip().lower()

    if provider_lower == "openai":
        return {
            "provider": "openai",
            "family": family or "gpt",
            "supportedAuthTypes": ["bearer"],
            "defaultAuthType": "bearer",
            "authDefaults": {
                "bearer": {"helpText": "OpenAI API key from https://platform.openai.com/api-keys"}
            },
            "recommendedHeaders": {}
        }

    if provider_lower == "anthropic":
        return {
            "provider": "anthropic",
            "family": family or "claude",
            "supportedAuthTypes": ["bearer"],
            "defaultAuthType": "bearer",
            "authDefaults": {
                "bearer": {"helpText": "Anthropic API key from https://console.anthropic.com/settings/keys"}
            },
            "recommendedHeaders": {}
        }

    if provider_lower == "google":
        return {
            "provider": "google",
            "family": family or "gemini",
            "supportedAuthTypes": ["header"],
            "defaultAuthType": "header",
            "authDefaults": {
                "header": {
                    "headerName": "x-goog-api-key",
                    "helpText": "Gemini API key from Google AI Studio"
                }
            },
            "recommendedHeaders": {},
            "validation": {
                "header": {
                    "requiredHeaderName": "x-goog-api-key",
                    "errorMessage": "Gemini models require header name 'x-goog-api-key'"
                }
            },
            "parameterSchema": GEMINI_PARAMETER_SCHEMA,
            "parameterDefaults": GEMINI_PARAMETER_DEFAULTS
        }

    if provider_lower == "openrouter":
        return {
            "provider": "openrouter",
            "family": family or "openrouter",
            "supportedAuthTypes": ["bearer", "multi_header"],
            "defaultAuthType": "bearer",
            "authDefaults": {
                "bearer": {"helpText": "OpenRouter API key from https://openrouter.ai/keys"},
                "multi_header": {
                    "headers": [
                        {"name": "Authorization", "required": True, "helpText": "Bearer token"},
                        {"name": "HTTP-Referer", "required": False, "helpText": "Optional: Your site URL"},
                        {"name": "X-Title", "required": False, "helpText": "Optional: Your app name"}
                    ]
                }
            },
            "recommendedHeaders": {"HTTP-Referer": "", "X-Title": "XEditor"}
        }

    if provider_lower == "ollama":
        return {
            "provider": "ollama",
            "family": family or "",
            "supportedAuthTypes": ["none"],
            "defaultAuthType": "none",
            "authDefaults": {"none": {"helpText": "Ollama runs locally without authentication"}},
            "recommendedHeaders": {},
            "parameterSchema": OLLAMA_PARAMETER_SCHEMA,
            "parameterDefaults": OLLAMA_PARAMETER_DEFAULTS
        }

    if provider_lower == "lmstudio":
        return {
            "provider": "lmstudio",
            "family": family or "",
            "supportedAuthTypes": ["none", "bearer"],
            "defaultAuthType": "none",
            "authDefaults": {
                "none": {"helpText": "LM Studio typically runs locally without authentication"},
                "bearer": {"helpText": "Optional: API key if LM Studio has authentication"}
            },
            "recommendedHeaders": {},
            "parameterSchema": LMSTUDIO_PARAMETER_SCHEMA,
            "parameterDefaults": LMSTUDIO_PARAMETER_DEFAULTS
        }

    if provider_lower == "vllm":
        return {
            "provider": "vllm",
            "family": family or "",
            "supportedAuthTypes": ["none", "bearer"],
            "defaultAuthType": "none",
            "authDefaults": {
                "none": {"helpText": "vLLM typically runs locally without authentication"},
                "bearer": {"helpText": "Optional: API key if vLLM has authentication"}
            },
            "recommendedHeaders": {}
        }

    if provider_lower == "sglang":
        return {
            "provider": "sglang",
            "family": family or "",
            "supportedAuthTypes": ["none", "bearer"],
            "defaultAuthType": "none",
            "authDefaults": {
                "none": {"helpText": "SGLang typically runs locally without authentication"},
                "bearer": {"helpText": "Optional: API key if SGLang has authentication"}
            },
            "recommendedHeaders": {}
        }

    if provider_lower == "kimi":
        return {
            "provider": "kimi",
            "family": family or "kimi",
            "supportedAuthTypes": ["bearer"],
            "defaultAuthType": "bearer",
            "authDefaults": {
                "bearer": {"helpText": "Kimi API key from https://platform.moonshot.cn/"}
            },
            "recommendedHeaders": {}
        }

    if provider_lower == "openai_compatible":
        return {
            "provider": "openai_compatible",
            "family": family or "",
            "supportedAuthTypes": ["none", "bearer", "header", "query_param", "multi_header"],
            "defaultAuthType": "bearer",
            "authDefaults": {
                "bearer": {"helpText": "API key for your OpenAI-compatible endpoint"}
            },
            "recommendedHeaders": {}
        }

    if provider_lower == "local_companion":
        return {
            "provider": "local_companion",
            "family": family or "",
            "supportedAuthTypes": ["none"],
            "defaultAuthType": "none",
            "authDefaults": {"none": {"helpText": "Local Companion handles connection internally"}},
            "recommendedHeaders": {}
        }

    return None


def list_provider_presets() -> List[Dict[str, Any]]:
    """List all provider presets for UI. Derived from catalog + auth config."""
    presets: List[Dict[str, Any]] = []
    for entry in LITELLM_PROVIDER_CATALOG:
        preset = get_provider_preset(entry["id"])
        if preset:
            preset["id"] = entry["id"]
            preset["label"] = entry.get("label", entry["id"])
            preset["helpText"] = entry.get("helpText", "")
            presets.append(preset)
    return presets


async def handle_list_provider_presets(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """RPC handler for listing provider presets."""
    presets = list_provider_presets()
    providers = list_providers()

    if payload:
        provider = payload.get("provider")
        family = payload.get("family")
        if provider or family:
            specific = get_provider_preset(provider or "", family=family)
            if specific:
                return {
                    "success": True,
                    "preset": specific,
                    "providers": providers,
                    "allPresets": presets
                }

    return {
        "success": True,
        "providers": providers,
        "presets": presets
    }
