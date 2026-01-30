"""
Provider Presets Registry for XEditor Local Companion.
Defines authentication requirements, defaults, and parameter schemas for different LLM providers.
"""

from typing import Dict, Any, List, Optional
from urllib.parse import urlparse


# ─────────────────────────────────────────────────────────────────────────────
# Provider Registry - Source of truth for available providers
# ─────────────────────────────────────────────────────────────────────────────

PROVIDER_REGISTRY: List[Dict[str, Any]] = [
    {"id": "openai", "label": "OpenAI"},
    {"id": "anthropic", "label": "Anthropic"},
    {"id": "ollama", "label": "Ollama"},
    {"id": "lmstudio", "label": "LM Studio"},
    {"id": "vllm", "label": "vLLM"},
    {"id": "sglang", "label": "SGLang"},
    {"id": "openai_compatible", "label": "OpenAI Compatible"},
    {"id": "kimi", "label": "Kimi"},
    {"id": "local_companion", "label": "Local Companion"},
]


def list_providers() -> List[Dict[str, Any]]:
    """
    List all available LLM providers.
    Returns a list of provider definitions with id and label.
    """
    return PROVIDER_REGISTRY.copy()


# ─────────────────────────────────────────────────────────────────────────────
# Parameter Schema Definitions
# ─────────────────────────────────────────────────────────────────────────────

# Parameter schema field types:
# - "boolean": checkbox/toggle
# - "select": dropdown with options
# - "number": numeric input
# - "string": text input
#
# Each field can have:
# - id: unique identifier (used as key in providerParams, supports dot notation for nesting)
# - label: display label
# - type: field type
# - options: for select type, list of {value, label}
# - default: default value
# - helpText: optional help text
# - dependsOn: optional field id + value that must be set for this field to be visible

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
    "reasoning": {
        "enabled": False,
        "effort": "medium"
    }
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
        "helpText": "Thinking level for Gemini models. Flash supports: minimal, low, medium, high. Pro supports: low, high.",
        "dependsOn": {"field": "thinking.enabled", "value": True}
    }
]

GEMINI_PARAMETER_DEFAULTS: Dict[str, Any] = {
    "thinking": {
        "enabled": False,
        "thinkingLevel": "low"
    }
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
    "thinking": {
        "enabled": False
    }
}


def get_provider_parameter_schema(provider: str) -> Optional[List[Dict[str, Any]]]:
    """Get the parameter schema for a provider."""
    provider_lower = provider.lower()
    if provider_lower == "lmstudio":
        return LMSTUDIO_PARAMETER_SCHEMA
    if provider_lower == "gemini" or provider_lower == "openai_compatible":
        # Return Gemini schema for openai_compatible when family is gemini
        # This will be handled by get_provider_preset which checks family
        return None
    if provider_lower == "ollama":
        return OLLAMA_PARAMETER_SCHEMA
    return None


def get_provider_parameter_defaults(provider: str) -> Optional[Dict[str, Any]]:
    """Get the parameter defaults for a provider."""
    provider_lower = provider.lower()
    if provider_lower == "lmstudio":
        return LMSTUDIO_PARAMETER_DEFAULTS.copy()
    if provider_lower == "ollama":
        return OLLAMA_PARAMETER_DEFAULTS.copy()
    return None


# ─────────────────────────────────────────────────────────────────────────────
# Provider Presets
# ─────────────────────────────────────────────────────────────────────────────

def get_provider_preset(provider: str, base_url: Optional[str] = None, family: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """
    Get provider preset configuration for a given provider/baseUrl/family.
    Returns None if no preset matches.
    """
    # Check by baseUrl host first (most specific)
    if base_url:
        try:
            parsed = urlparse(base_url)
            host = parsed.netloc.lower()
            
            # Google Generative Language (Gemini)
            if "generativelanguage.googleapis.com" in host:
                return {
                    "provider": "openai_compatible",
                    "family": family or "gemini",
                    "supportedAuthTypes": ["header"],
                    "defaultAuthType": "header",
                    "authDefaults": {
                        "header": {
                            "headerName": "x-goog-api-key",
                            "helpText": "Gemini API key from Google AI Studio. Set as custom header with name 'x-goog-api-key'."
                        }
                    },
                    "recommendedHeaders": {},
                    "validation": {
                        "header": {
                            "requiredHeaderName": "x-goog-api-key",
                            "errorMessage": "Gemini models require header name 'x-goog-api-key'"
                        }
                    }
                }
            
            # Kimi API
            if "kimi-k2.ai" in host or "kimi.moonshot.cn" in host:
                return {
                    "provider": "openai_compatible",
                    "family": family or "kimi",
                    "supportedAuthTypes": ["bearer"],
                    "defaultAuthType": "bearer",
                    "authDefaults": {
                        "bearer": {
                            "helpText": "Kimi API key. Get one from https://platform.moonshot.cn/"
                        }
                    },
                    "recommendedHeaders": {}
                }
            
            # OpenRouter
            if "openrouter.ai" in host:
                return {
                    "provider": "openai_compatible",
                    "family": family or "openrouter",
                    "supportedAuthTypes": ["bearer", "multi_header"],
                    "defaultAuthType": "bearer",
                    "authDefaults": {
                        "bearer": {
                            "helpText": "OpenRouter API key. Get one at https://openrouter.ai/keys"
                        },
                        "multi_header": {
                            "headers": [
                                {"name": "Authorization", "required": True, "helpText": "Bearer token: Bearer YOUR_API_KEY"},
                                {"name": "HTTP-Referer", "required": False, "helpText": "Optional: Your site URL for analytics"},
                                {"name": "X-Title", "required": False, "helpText": "Optional: Your app name"}
                            ]
                        }
                    },
                    "recommendedHeaders": {
                        "HTTP-Referer": "",
                        "X-Title": "XEditor"
                    }
                }
        except Exception:
            pass
    
    # Check by provider ID
    provider_lower = provider.lower()
    
    if provider_lower == "openai":
        return {
            "provider": "openai",
            "family": family or "gpt",
            "supportedAuthTypes": ["bearer"],
            "defaultAuthType": "bearer",
            "authDefaults": {
                "bearer": {
                    "helpText": "OpenAI API key from https://platform.openai.com/api-keys"
                }
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
                "bearer": {
                    "helpText": "Anthropic API key from https://console.anthropic.com/settings/keys"
                }
            },
            "recommendedHeaders": {}
        }
    
    if provider_lower == "lmstudio":
        return {
            "provider": "lmstudio",
            "family": family or "",
            "supportedAuthTypes": ["none", "bearer"],
            "defaultAuthType": "none",
            "authDefaults": {
                "none": {
                    "helpText": "LM Studio typically runs locally without authentication"
                },
                "bearer": {
                    "helpText": "Optional: API key if LM Studio is configured with authentication"
                }
            },
            "recommendedHeaders": {},
            "parameterSchema": LMSTUDIO_PARAMETER_SCHEMA,
            "parameterDefaults": LMSTUDIO_PARAMETER_DEFAULTS
        }
    
    if provider_lower == "ollama":
        return {
            "provider": "ollama",
            "family": family or "",
            "supportedAuthTypes": ["none"],
            "defaultAuthType": "none",
            "authDefaults": {
                "none": {
                    "helpText": "Ollama runs locally without authentication"
                }
            },
            "recommendedHeaders": {},
            "parameterSchema": OLLAMA_PARAMETER_SCHEMA,
            "parameterDefaults": OLLAMA_PARAMETER_DEFAULTS
        }
    
    if provider_lower == "vllm":
        return {
            "provider": "vllm",
            "family": family or "",
            "supportedAuthTypes": ["none", "bearer"],
            "defaultAuthType": "none",
            "authDefaults": {
                "none": {
                    "helpText": "vLLM typically runs locally without authentication"
                },
                "bearer": {
                    "helpText": "Optional: API key if vLLM is configured with authentication"
                }
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
                "none": {
                    "helpText": "SGLang typically runs locally without authentication"
                },
                "bearer": {
                    "helpText": "Optional: API key if SGLang is configured with authentication"
                }
            },
            "recommendedHeaders": {}
        }
    
    if provider_lower == "kimi":
        return {
            "provider": "openai_compatible",
            "family": family or "kimi",
            "supportedAuthTypes": ["bearer"],
            "defaultAuthType": "bearer",
            "authDefaults": {
                "bearer": {
                    "helpText": "Kimi API key. Get one from https://platform.moonshot.cn/"
                }
            },
            "recommendedHeaders": {}
        }
    
    if provider_lower == "local_companion":
        return {
            "provider": "local_companion",
            "family": family or "",
            "supportedAuthTypes": ["none"],
            "defaultAuthType": "none",
            "authDefaults": {
                "none": {
                    "helpText": "Local Companion handles connection internally"
                }
            },
            "recommendedHeaders": {}
        }
    
    # Check by family
    if family:
        family_lower = family.lower()
        
        if family_lower == "gemini":
            return {
                "provider": "openai_compatible",
                "family": "gemini",
                "supportedAuthTypes": ["header"],
                "defaultAuthType": "header",
                "authDefaults": {
                    "header": {
                        "headerName": "x-goog-api-key",
                        "helpText": "Gemini API key from Google AI Studio. Set as custom header with name 'x-goog-api-key'."
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
        
        if family_lower == "kimi":
            return {
                "provider": "openai_compatible",
                "family": "kimi",
                "supportedAuthTypes": ["bearer"],
                "defaultAuthType": "bearer",
                "authDefaults": {
                    "bearer": {
                        "helpText": "Kimi API key. Get one from https://platform.moonshot.cn/"
                    }
                },
                "recommendedHeaders": {}
            }
    
    return None


def list_provider_presets() -> List[Dict[str, Any]]:
    """
    List all available provider presets.
    Returns a list of preset configurations with auth and parameter info.
    """
    presets = [
        {
            "id": "openai",
            "provider": "openai",
            "family": "gpt",
            "supportedAuthTypes": ["bearer"],
            "defaultAuthType": "bearer",
            "authDefaults": {
                "bearer": {
                    "helpText": "OpenAI API key from https://platform.openai.com/api-keys"
                }
            },
            "recommendedHeaders": {}
        },
        {
            "id": "anthropic",
            "provider": "anthropic",
            "family": "claude",
            "supportedAuthTypes": ["bearer"],
            "defaultAuthType": "bearer",
            "authDefaults": {
                "bearer": {
                    "helpText": "Anthropic API key from https://console.anthropic.com/settings/keys"
                }
            },
            "recommendedHeaders": {}
        },
        {
            "id": "lmstudio",
            "provider": "lmstudio",
            "family": "",
            "supportedAuthTypes": ["none", "bearer"],
            "defaultAuthType": "none",
            "authDefaults": {
                "none": {
                    "helpText": "LM Studio typically runs locally without authentication"
                },
                "bearer": {
                    "helpText": "Optional: API key if LM Studio is configured with authentication"
                }
            },
            "recommendedHeaders": {},
            "parameterSchema": LMSTUDIO_PARAMETER_SCHEMA,
            "parameterDefaults": LMSTUDIO_PARAMETER_DEFAULTS
        },
        {
            "id": "ollama",
            "provider": "ollama",
            "family": "",
            "supportedAuthTypes": ["none"],
            "defaultAuthType": "none",
            "authDefaults": {
                "none": {
                    "helpText": "Ollama runs locally without authentication"
                }
            },
            "recommendedHeaders": {},
            "parameterSchema": OLLAMA_PARAMETER_SCHEMA,
            "parameterDefaults": OLLAMA_PARAMETER_DEFAULTS
        },
        {
            "id": "vllm",
            "provider": "vllm",
            "family": "",
            "supportedAuthTypes": ["none", "bearer"],
            "defaultAuthType": "none",
            "authDefaults": {
                "none": {
                    "helpText": "vLLM typically runs locally without authentication"
                },
                "bearer": {
                    "helpText": "Optional: API key if vLLM is configured with authentication"
                }
            },
            "recommendedHeaders": {}
        },
        {
            "id": "sglang",
            "provider": "sglang",
            "family": "",
            "supportedAuthTypes": ["none", "bearer"],
            "defaultAuthType": "none",
            "authDefaults": {
                "none": {
                    "helpText": "SGLang typically runs locally without authentication"
                },
                "bearer": {
                    "helpText": "Optional: API key if SGLang is configured with authentication"
                }
            },
            "recommendedHeaders": {}
        },
        {
            "id": "gemini",
            "provider": "openai_compatible",
            "family": "gemini",
            "supportedAuthTypes": ["header"],
            "defaultAuthType": "header",
            "authDefaults": {
                "header": {
                    "headerName": "x-goog-api-key",
                    "helpText": "Gemini API key from Google AI Studio. Set as custom header with name 'x-goog-api-key'."
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
        },
        {
            "id": "kimi",
            "provider": "openai_compatible",
            "family": "kimi",
            "supportedAuthTypes": ["bearer"],
            "defaultAuthType": "bearer",
            "authDefaults": {
                "bearer": {
                    "helpText": "Kimi API key. Get one from https://platform.moonshot.cn/"
                }
            },
            "recommendedHeaders": {}
        },
        {
            "id": "openrouter",
            "provider": "openai_compatible",
            "family": "openrouter",
            "supportedAuthTypes": ["bearer", "multi_header"],
            "defaultAuthType": "bearer",
            "authDefaults": {
                "bearer": {
                    "helpText": "OpenRouter API key. Get one at https://openrouter.ai/keys"
                },
                "multi_header": {
                    "headers": [
                        {"name": "Authorization", "required": True, "helpText": "Bearer token: Bearer YOUR_API_KEY"},
                        {"name": "HTTP-Referer", "required": False, "helpText": "Optional: Your site URL for analytics"},
                        {"name": "X-Title", "required": False, "helpText": "Optional: Your app name"}
                    ]
                }
            },
            "recommendedHeaders": {
                "HTTP-Referer": "",
                "X-Title": "XEditor"
            }
        },
        {
            "id": "local_companion",
            "provider": "local_companion",
            "family": "",
            "supportedAuthTypes": ["none"],
            "defaultAuthType": "none",
            "authDefaults": {
                "none": {
                    "helpText": "Local Companion handles connection internally"
                }
            },
            "recommendedHeaders": {}
        },
        {
            "id": "openai_compatible",
            "provider": "openai_compatible",
            "family": "",
            "supportedAuthTypes": ["none", "bearer", "header", "query_param", "multi_header"],
            "defaultAuthType": "bearer",
            "authDefaults": {
                "bearer": {
                    "helpText": "API key for your OpenAI-compatible endpoint"
                }
            },
            "recommendedHeaders": {}
        }
    ]
    
    return presets


# RPC Handler
async def handle_list_provider_presets(payload: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    RPC handler for listing all provider presets.
    Always returns the list of providers.
    Optionally filters by provider/baseUrl/family if provided in payload.
    """
    presets = list_provider_presets()
    providers = list_providers()
    
    # If payload specifies provider/baseUrl/family, try to get a specific preset
    if payload:
        provider = payload.get("provider")
        base_url = payload.get("baseUrl")
        family = payload.get("family")
        
        if provider or base_url or family:
            specific = get_provider_preset(provider or "", base_url, family)
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
