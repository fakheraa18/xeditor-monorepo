"""
Structured events for LLM provider responses.

These dataclasses provide a normalized interface between providers and consumers,
decoupling provider-specific wire formats from the rest of the system.
"""

from dataclasses import dataclass, field
from typing import Literal, Optional, Dict, Any


@dataclass
class TokenUsage:
    """
    Normalized token usage from any LLM provider.
    
    All providers must return this structure regardless of their native format:
    - OpenAI: prompt_tokens, completion_tokens, total_tokens
    - Ollama: prompt_eval_count -> prompt_tokens, eval_count -> completion_tokens
    - LMStudio: input_tokens -> prompt_tokens, output_tokens -> completion_tokens
    - Gemini: promptTokenCount -> prompt_tokens, candidatesTokenCount -> completion_tokens
    """
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    
    # Optional detailed breakdown (provider-specific)
    cached_tokens: Optional[int] = None  # LMStudio: input_tokens_details.cached_tokens
    reasoning_tokens: Optional[int] = None  # LMStudio: output_tokens_details.reasoning_tokens
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization (snake_case for server)."""
        result: Dict[str, Any] = {
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
        }
        if self.cached_tokens is not None:
            result["cached_tokens"] = self.cached_tokens
        if self.reasoning_tokens is not None:
            result["reasoning_tokens"] = self.reasoning_tokens
        return result
    
    def to_camel_case_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for client (camelCase)."""
        result: Dict[str, Any] = {
            "promptTokens": self.prompt_tokens,
            "completionTokens": self.completion_tokens,
            "totalTokens": self.total_tokens,
        }
        if self.cached_tokens is not None:
            result["cachedTokens"] = self.cached_tokens
        if self.reasoning_tokens is not None:
            result["reasoningTokens"] = self.reasoning_tokens
        return result
    
    @classmethod
    def from_openai(cls, usage: Optional[Dict[str, Any]]) -> Optional["TokenUsage"]:
        """Parse from OpenAI/Anthropic format."""
        if not usage:
            return None
        return cls(
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            total_tokens=usage.get("total_tokens", 0),
        )
    
    @classmethod
    def from_ollama(cls, data: Dict[str, Any]) -> Optional["TokenUsage"]:
        """Parse from Ollama format (prompt_eval_count, eval_count)."""
        if "prompt_eval_count" not in data and "eval_count" not in data:
            return None
        prompt = data.get("prompt_eval_count", 0)
        completion = data.get("eval_count", 0)
        return cls(
            prompt_tokens=prompt,
            completion_tokens=completion,
            total_tokens=prompt + completion,
        )
    
    @classmethod
    def from_lmstudio(cls, usage: Optional[Dict[str, Any]]) -> Optional["TokenUsage"]:
        """Parse from LMStudio format (input_tokens, output_tokens, with details)."""
        if not usage:
            return None
        
        prompt = usage.get("input_tokens", 0)
        completion = usage.get("output_tokens", 0)
        total = usage.get("total_tokens", prompt + completion)
        
        # Extract detailed token info
        cached = None
        reasoning = None
        
        input_details = usage.get("input_tokens_details", {})
        if isinstance(input_details, dict):
            cached = input_details.get("cached_tokens")
        
        output_details = usage.get("output_tokens_details", {})
        if isinstance(output_details, dict):
            reasoning = output_details.get("reasoning_tokens")
        
        return cls(
            prompt_tokens=prompt,
            completion_tokens=completion,
            total_tokens=total,
            cached_tokens=cached,
            reasoning_tokens=reasoning,
        )
    
    @classmethod
    def from_gemini(cls, usage_metadata: Optional[Dict[str, Any]]) -> Optional["TokenUsage"]:
        """Parse from Gemini usageMetadata format."""
        if not usage_metadata:
            return None
        
        prompt = usage_metadata.get("promptTokenCount", 0)
        completion = usage_metadata.get("candidatesTokenCount", 0)
        total = usage_metadata.get("totalTokenCount", prompt + completion)
        cached = usage_metadata.get("cachedContentTokenCount")
        
        return cls(
            prompt_tokens=prompt,
            completion_tokens=completion,
            total_tokens=total,
            cached_tokens=cached,
        )
    
    @classmethod
    def from_auto(cls, usage: Optional[Dict[str, Any]]) -> Optional["TokenUsage"]:
        """Auto-detect format and parse accordingly."""
        if not usage:
            return None
        
        # Ollama format
        if "prompt_eval_count" in usage or "eval_count" in usage:
            return cls.from_ollama(usage)
        
        # Gemini format
        if "promptTokenCount" in usage or "candidatesTokenCount" in usage:
            return cls.from_gemini(usage)
        
        # LMStudio format (input_tokens/output_tokens)
        if "input_tokens" in usage or "output_tokens" in usage:
            return cls.from_lmstudio(usage)
        
        # Default: OpenAI format
        return cls.from_openai(usage)


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
        """Create from dictionary (e.g., from apps.code_editor.agent_runner payload)."""
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
