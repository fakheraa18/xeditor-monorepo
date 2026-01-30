"""
LM Studio provider.

Handles LM Studio's /v1/responses endpoint which supports structured reasoning output.
This provider extracts reasoning from the provider-specific format and emits it
as structured thinking events (not injected as text tags).
"""

import json
from typing import AsyncGenerator, Dict, Any, List

import httpx

from .base import LLMProvider
from .events import LLMEvent, LLMRequest, TokenUsage


def extract_reasoning_text(output_item: Dict[str, Any]) -> str:
    """Extract reasoning text from LM Studio reasoning output item."""
    content_parts = output_item.get("content", [])
    reasoning_parts: List[str] = []
    for part in content_parts:
        if part.get("type") == "reasoning_text":
            reasoning_parts.append(part.get("text", ""))
    return "\n".join(reasoning_parts)


def extract_content_text(output_item: Dict[str, Any]) -> str:
    """Extract message content from LM Studio message output item."""
    content_parts = output_item.get("content", [])
    for part in content_parts:
        if part.get("type") == "output_text":
            return part.get("text", "")
    return ""


def convert_messages_to_input(messages: List[Dict[str, Any]]) -> str:
    """Convert OpenAI-style messages to LM Studio input string format."""
    input_parts: List[str] = []
    for msg in messages:
        role = msg.get("role", "")
        content = msg.get("content", "")
        if role == "system":
            input_parts.append(f"System: {content}")
        elif role == "user":
            input_parts.append(f"User: {content}")
        elif role == "assistant":
            input_parts.append(f"Assistant: {content}")
    return "\n\n".join(input_parts)


class LMStudioProvider(LLMProvider):
    """
    Provider for LM Studio with reasoning support.
    
    When reasoning is enabled, uses /v1/responses endpoint which returns
    structured reasoning output. Otherwise falls back to OpenAI-compatible
    /v1/chat/completions endpoint.
    
    Reasoning can be enabled via:
    - provider_params: {"reasoning": {"enabled": True, "effort": "medium"}}
    - extra_payload (legacy): {"reasoning": {"effort": "medium"}}
    """
    
    def _get_reasoning_config(self, request: LLMRequest) -> Dict[str, Any] | None:
        """
        Get reasoning configuration from provider_params or extra_payload.
        
        Returns the reasoning config dict if enabled, None otherwise.
        Priority: provider_params > extra_payload (for backward compatibility)
        """
        # Check provider_params first (new structured approach)
        reasoning_params = request.provider_params.get("reasoning", {})
        if reasoning_params.get("enabled", False):
            # Build reasoning config for LM Studio
            return {
                "effort": reasoning_params.get("effort", "medium")
            }
        
        # Fallback: check extra_payload for legacy "reasoning" key
        if "reasoning" in request.extra_payload:
            return request.extra_payload["reasoning"]
        
        return None
    
    async def stream(self, request: LLMRequest) -> AsyncGenerator[LLMEvent, None]:
        """Stream response from LM Studio."""
        base_url = self.get_base_url()
        
        if not base_url:
            yield LLMEvent(
                type="error",
                error="No baseUrl provided for LM Studio. Please configure the connection settings."
            )
            return
        
        # Check if reasoning is requested (from provider_params or extra_payload)
        reasoning_config = self._get_reasoning_config(request)
        
        if reasoning_config:
            # Use /v1/responses endpoint for reasoning support
            async for event in self._stream_with_reasoning(request, reasoning_config):
                yield event
        else:
            # Use standard OpenAI-compatible streaming
            async for event in self._stream_openai_compatible(request):
                yield event
    
    async def _stream_with_reasoning(self, request: LLMRequest, reasoning_config: Dict[str, Any]) -> AsyncGenerator[LLMEvent, None]:
        """
        Use LM Studio's /v1/responses endpoint for reasoning.
        
        This endpoint is non-streaming but returns structured reasoning output.
        We emit the reasoning as thinking events and content as content events.
        
        Args:
            request: The LLM request
            reasoning_config: Reasoning configuration dict (e.g., {"effort": "medium"})
        """
        url = f"{self.get_base_url().rstrip('/')}/v1/responses"
        
        headers = self.get_headers()
        headers, url = self.apply_auth(headers, url)
        
        # Build request body for /v1/responses
        request_body: Dict[str, Any] = {
            "model": request.model_id,
            "input": convert_messages_to_input(request.messages),
        }
        
        if request.temperature is not None:
            request_body["temperature"] = request.temperature
        
        # Add reasoning config (from provider_params or extra_payload)
        request_body["reasoning"] = reasoning_config
        
        # Merge remaining extra payload (excluding "reasoning" since we already added it)
        if request.extra_payload:
            for key, value in request.extra_payload.items():
                if key != "reasoning":
                    request_body[key] = value
        
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                response = await client.post(url, json=request_body, headers=headers)
                response.raise_for_status()
                data = response.json()
                
                reasoning_content = ""
                message_content = ""
                usage = None
                
                # Extract reasoning and message from output
                for output_item in data.get("output", []):
                    output_type = output_item.get("type", "")
                    
                    if output_type == "reasoning":
                        reasoning_content = extract_reasoning_text(output_item)
                    elif output_type == "message":
                        message_content = extract_content_text(output_item)
                
                # Extract and normalize usage using TokenUsage dataclass
                if "usage" in data:
                    token_usage = TokenUsage.from_lmstudio(data["usage"])
                    usage = token_usage.to_dict() if token_usage else None
                
                # Emit thinking events first (if reasoning present)
                # This is the key difference from the old approach:
                # We emit structured thinking events instead of injecting <think> tags
                if reasoning_content:
                    # Stream reasoning in chunks to simulate streaming UX
                    chunk_size = 50
                    for i in range(0, len(reasoning_content), chunk_size):
                        chunk = reasoning_content[i:i + chunk_size]
                        yield LLMEvent(type="thinking", content=chunk)
                
                # Emit content events
                if message_content:
                    # Stream content in chunks
                    chunk_size = 10
                    for i in range(0, len(message_content), chunk_size):
                        chunk = message_content[i:i + chunk_size]
                        yield LLMEvent(type="content", content=chunk)
                
                yield LLMEvent(
                    type="end",
                    usage=usage,
                    finish_reason="stop",
                )
                
        except httpx.HTTPStatusError as http_error:
            status_code = http_error.response.status_code
            if status_code == 401:
                error_message = "Authentication failed (401 Unauthorized). Please check your API key or credentials."
            elif status_code == 403:
                error_message = "Access forbidden (403). Please check your API key permissions."
            elif status_code == 404:
                error_message = "Endpoint not found (404). LM Studio /v1/responses endpoint may not be available."
            else:
                error_message = f"HTTP error {status_code}: {str(http_error)}"
            yield LLMEvent(type="error", error=error_message)
            
        except httpx.RequestError as request_error:
            error_message = f"Connection error: {str(request_error)}. Please check your network connection and LM Studio is running."
            yield LLMEvent(type="error", error=error_message)
            
        except Exception as e:
            yield LLMEvent(type="error", error=f"LM Studio request failed: {str(e)}")
    
    async def _stream_openai_compatible(self, request: LLMRequest) -> AsyncGenerator[LLMEvent, None]:
        """Use standard OpenAI-compatible streaming endpoint."""
        url = self.build_url() or f"{self.get_base_url().rstrip('/')}/v1/chat/completions"
        
        headers = self.get_headers()
        headers, url = self.apply_auth(headers, url)
        
        # Build OpenAI-compatible request body
        request_body: Dict[str, Any] = {
            "model": request.model_id,
            "messages": request.messages,
            "temperature": request.temperature,
            "stream": True,
        }
        
        if request.max_tokens:
            request_body["max_tokens"] = request.max_tokens
        
        # Merge extra payload
        if request.extra_payload:
            request_body.update(request.extra_payload)
        
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream("POST", url, json=request_body, headers=headers) as response:
                    response.raise_for_status()
                    
                    full_content = ""
                    finish_reason = None
                    usage = None
                    
                    async for line in response.aiter_lines():
                        if not line.strip() or line == "data: [DONE]":
                            continue
                        
                        if line.startswith("data: "):
                            data_str = line[6:]
                            try:
                                data = json.loads(data_str)
                                
                                if "choices" in data and len(data["choices"]) > 0:
                                    delta = data["choices"][0].get("delta", {})
                                    
                                    if "content" in delta:
                                        chunk = delta["content"]
                                        full_content += chunk
                                        yield LLMEvent(type="content", content=chunk)
                                    
                                    # Detect OpenAI-style tool calls in delta
                                    # Note: Tool calls come incrementally, so we accumulate them by ID
                                    # For simplicity, we emit when we have both name and valid JSON arguments
                                    if "tool_calls" in delta and isinstance(delta["tool_calls"], list):
                                        for tool_call_delta in delta["tool_calls"]:
                                            if not isinstance(tool_call_delta, dict):
                                                continue
                                            fn = tool_call_delta.get("function", {})
                                            if not isinstance(fn, dict):
                                                continue
                                            name = fn.get("name")
                                            args_str = fn.get("arguments", "")
                                            
                                            # Only emit if we have a name and complete JSON arguments
                                            # Incomplete tool calls will be handled by parser fallback
                                            if name and args_str:
                                                try:
                                                    args = json.loads(args_str)
                                                    # Valid JSON - emit structured tool_call event
                                                    yield LLMEvent(
                                                        type="tool_call",
                                                        tool_call={
                                                            "tool": name,
                                                            "args": args,
                                                        }
                                                    )
                                                except json.JSONDecodeError:
                                                    # Partial JSON - skip for now, parser will handle it
                                                    pass
                                    
                                    if "finish_reason" in data["choices"][0]:
                                        finish_reason = data["choices"][0]["finish_reason"]
                                
                                if "usage" in data:
                                    # Auto-detect format (could be OpenAI or LMStudio style)
                                    token_usage = TokenUsage.from_auto(data["usage"])
                                    usage = token_usage.to_dict() if token_usage else None
                            except json.JSONDecodeError:
                                pass
                    
                    yield LLMEvent(
                        type="end",
                        usage=usage,
                        finish_reason=finish_reason,
                    )
                    
        except httpx.HTTPStatusError as http_error:
            status_code = http_error.response.status_code
            error_message = f"HTTP error {status_code}: {str(http_error)}"
            yield LLMEvent(type="error", error=error_message)
            
        except httpx.RequestError as request_error:
            error_message = f"Connection error: {str(request_error)}. Please check your network connection and LM Studio is running."
            yield LLMEvent(type="error", error=error_message)
            
        except Exception as e:
            yield LLMEvent(type="error", error=f"LM Studio streaming failed: {str(e)}")
