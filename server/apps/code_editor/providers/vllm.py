"""
vLLM provider.

Handles local vLLM server routing for the local_companion provider type.
"""

import json
from typing import AsyncGenerator, Dict, Any

import httpx

from .base import LLMProvider
from .events import LLMEvent, LLMRequest, TokenUsage


class VLLMProvider(LLMProvider):
    """
    Provider for local vLLM server.
    
    Routes requests to a locally running vLLM server managed by vllm_manager.
    Uses OpenAI-compatible API format.
    """
    
    async def stream(self, request: LLMRequest) -> AsyncGenerator[LLMEvent, None]:
        """Stream response from local vLLM server."""
        try:
            # Import vllm_manager to check status
            from apps.code_editor.vllm_manager import get_vllm_manager
            manager = get_vllm_manager()
            status = manager.get_status()
            
            if not status["available"]:
                yield LLMEvent(
                    type="error",
                    error="vLLM is not available on this platform (requires Linux + CUDA)"
                )
                return
            
            if not status["running"]:
                yield LLMEvent(
                    type="error",
                    error="vLLM server is not running. Start it first using vllm_start RPC."
                )
                return
            
            # Route to local vLLM server
            vllm_url = f"http://127.0.0.1:{status['port']}/v1/chat/completions"
            
            # Build request body (OpenAI-compatible)
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
            
            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream("POST", vllm_url, json=request_body) as response:
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
                                    
                                    if "finish_reason" in data["choices"][0]:
                                        finish_reason = data["choices"][0]["finish_reason"]
                                
                                if "usage" in data:
                                    # Normalize usage using TokenUsage dataclass
                                    token_usage = TokenUsage.from_openai(data["usage"])
                                    usage = token_usage.to_dict() if token_usage else None
                            except json.JSONDecodeError:
                                pass
                    
                    yield LLMEvent(
                        type="end",
                        usage=usage,
                        finish_reason=finish_reason,
                    )
                    
        except ImportError:
            yield LLMEvent(
                type="error",
                error="vLLM manager not available. vLLM support requires additional dependencies."
            )
            
        except httpx.HTTPStatusError as http_error:
            status_code = http_error.response.status_code
            error_message = f"vLLM HTTP error {status_code}: {str(http_error)}"
            yield LLMEvent(type="error", error=error_message)
            
        except httpx.RequestError as request_error:
            error_message = f"vLLM connection error: {str(request_error)}. Please check if vLLM server is running."
            yield LLMEvent(type="error", error=error_message)
            
        except Exception as e:
            yield LLMEvent(type="error", error=f"vLLM request failed: {str(e)}")
