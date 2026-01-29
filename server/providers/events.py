"""
Structured events for LLM provider responses.

These dataclasses provide a normalized interface between providers and consumers,
decoupling provider-specific wire formats from the rest of the system.
"""

from dataclasses import dataclass, field
from typing import Literal, Optional, Dict, Any


@dataclass
class LLMEvent:
    """
    Normalized event from any LLM provider.
    
    Event types:
    - "thinking": Model's internal reasoning (extracted from provider-specific format)
    - "content": Regular content chunk for display/parsing
    - "tool_call": Structured tool call (preferred over text-based tool calls)
    - "end": Stream complete, includes usage stats
    - "error": Error occurred during streaming
    """
    type: Literal["thinking", "content", "tool_call", "end", "error"]
    content: Optional[str] = None  # For thinking/content chunks
    tool_call: Optional[Dict[str, Any]] = None  # For tool_call event: {"tool": str, "args": dict}
    usage: Optional[Dict[str, int]] = None  # For end event
    error: Optional[str] = None  # For error event
    finish_reason: Optional[str] = None  # For end event


@dataclass
class LLMResponse:
    """
    Non-streaming LLM response.
    
    Used when streaming is not needed or for collecting a stream into a single response.
    """
    content: str
    thinking: Optional[str] = None
    usage: Optional[Dict[str, int]] = None
    finish_reason: Optional[str] = None
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result: Dict[str, Any] = {
            "content": self.content,
        }
        if self.thinking:
            result["thinking"] = self.thinking
        if self.usage:
            result["usage"] = self.usage
        if self.finish_reason:
            result["finish_reason"] = self.finish_reason
        if self.error:
            result["error"] = self.error
        return result


@dataclass
class LLMRequest:
    """
    Normalized request to any LLM provider.
    
    Contains all the information a provider needs to make a request,
    abstracted from the specific wire format.
    """
    model_id: str
    messages: list = field(default_factory=list)
    temperature: float = 0.7
    max_tokens: Optional[int] = None
    extra_payload: Dict[str, Any] = field(default_factory=dict)
    
    # Provider-specific structured parameters (from model config providerParams)
    # These are translated by each provider into provider-specific request fields
    provider_params: Dict[str, Any] = field(default_factory=dict)
    
    # Provider-specific config (passed through from model config)
    provider: str = ""
    connection: Dict[str, Any] = field(default_factory=dict)
    auth: Dict[str, Any] = field(default_factory=dict)
    
    # Model metadata
    family: Optional[str] = None
    version: Optional[str] = None
    mode: Optional[str] = None
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "LLMRequest":
        """Create from dictionary (e.g., from agent_runner payload)."""
        return cls(
            model_id=data.get("modelId", ""),
            messages=data.get("messages", []),
            temperature=data.get("temperature", 0.7),
            max_tokens=data.get("maxTokens"),
            extra_payload=data.get("extraPayload", {}),
            provider_params=data.get("providerParams", {}),
            provider=data.get("provider", ""),
            connection=data.get("connection", {}),
            auth=data.get("auth", {}),
            family=data.get("family"),
            version=data.get("version"),
            mode=data.get("mode"),
        )
