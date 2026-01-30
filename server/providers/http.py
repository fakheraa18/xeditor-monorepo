"""
Generic HTTP provider for OpenAI-compatible endpoints.

This is the fallback provider for any endpoint that speaks OpenAI-compatible API.
"""

import json
from typing import AsyncGenerator, Dict, Any

import httpx

from .base import LLMProvider
from .events import LLMEvent, LLMRequest


class GenericHTTPProvider(LLMProvider):
    """
    Generic provider for OpenAI-compatible HTTP endpoints.
    
    This serves as a fallback for any endpoint that follows the OpenAI API format
    but isn't explicitly handled by other providers.
    """
    
    async def stream(self, request: LLMRequest) -> AsyncGenerator[LLMEvent, None]:
        """Stream response from OpenAI-compatible endpoint."""
        base_url = self.get_base_url()
        
        if not base_url:
            # Provide helpful error message
            provider = request.provider or "unknown"
            if provider in ["openai", "anthropic"]:
                error_message = f"API key is required for {provider.upper()} models. Please configure your API key in the model settings."
            else:
                error_message = f"No baseUrl provided for provider {provider}. Please configure the connection settings."
            yield LLMEvent(type="error", error=error_message)
            return
        
        # Build URL
        # For OpenRouter: normalize to ensure baseUrl=https://openrouter.ai and path=/api/v1/chat/completions
        # This handles cases where user configured baseUrl=https://openrouter.ai/api and path=/v1/chat/completions
        path = self.get_path()
        base_url_normalized = base_url.rstrip('/')
        
        if 'openrouter.ai' in base_url_normalized.lower():
            # If baseUrl includes /api, remove it and ensure path starts with /api
            if base_url_normalized.endswith('/api'):
                base_url_normalized = base_url_normalized[:-4]  # Remove /api from baseUrl
                if not path.startswith('/api'):
                    path = '/api' + path if path.startswith('/') else '/api/' + path
            # If baseUrl doesn't have /api, ensure path starts with /api
            elif not path.startswith('/api'):
                path = '/api' + path if path.startswith('/') else '/api/' + path
            
            # Construct URL manually with normalized values
            path_normalized = path.lstrip('/')
            url = f"{base_url_normalized}/{path_normalized}" if path_normalized else base_url_normalized
        else:
            # For non-OpenRouter, use standard build_url
            url = self.build_url() or f"{base_url.rstrip('/')}/v1/chat/completions"
        
        # Build headers and apply auth
        headers = self.get_headers()
        headers, url = self.apply_auth(headers, url)
        
        # Build request body (OpenAI-compatible format)
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
                    # Check for errors before streaming - read error response if status is not OK
                    if response.status_code >= 400:
                        # Read the error response before it's consumed by streaming
                        error_content = b""
                        async for chunk in response.aiter_bytes():
                            error_content += chunk
                            if len(error_content) > 10000:  # Limit to 10KB
                                break
                        
                        error_text = error_content.decode('utf-8', errors='ignore') if error_content else ""
                        error_data = None
                        try:
                            error_data = json.loads(error_text) if error_text else None
                        except:
                            pass
                        
                        # Store error data in response for later use in exception handler
                        response._error_data = error_data
                        response._error_text = error_text
                        
                        # Raise HTTPStatusError - but we've already consumed the stream
                        from httpx import HTTPStatusError
                        raise HTTPStatusError(
                            message=f"HTTP {response.status_code}",
                            request=response.request,
                            response=response
                        )
                    
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
                                    
                                    # Extract thinking/reasoning from delta (Kimi API uses "reasoning" field)
                                    if "reasoning" in delta and delta["reasoning"]:
                                        reasoning_chunk = delta["reasoning"]
                                        yield LLMEvent(type="thinking", content=reasoning_chunk)
                                    
                                    # Also check for "thinking" field (for other providers)
                                    if "thinking" in delta and delta["thinking"]:
                                        thinking_chunk = delta["thinking"]
                                        yield LLMEvent(type="thinking", content=thinking_chunk)
                                    
                                    if "content" in delta:
                                        chunk = delta["content"]
                                        full_content += chunk
                                        yield LLMEvent(type="content", content=chunk)
                                    
                                    if "finish_reason" in data["choices"][0]:
                                        finish_reason = data["choices"][0]["finish_reason"]
                                
                                if "usage" in data:
                                    usage = {
                                        "prompt_tokens": data["usage"].get("prompt_tokens", 0),
                                        "completion_tokens": data["usage"].get("completion_tokens", 0),
                                        "total_tokens": data["usage"].get("total_tokens", 0),
                                    }
                            except json.JSONDecodeError:
                                pass
                    
                    yield LLMEvent(
                        type="end",
                        usage=usage,
                        finish_reason=finish_reason,
                    )
                    
        except httpx.HTTPStatusError as http_error:
            status_code = http_error.response.status_code
            
            # Check if we already read the error data (from streaming response)
            error_json = None
            if hasattr(http_error.response, '_error_data'):
                error_json = http_error.response._error_data
            else:
                # Try to read error response - for non-streaming responses
                try:
                    error_body = http_error.response.text[:1000] if hasattr(http_error.response, 'text') else ""
                    if error_body:
                        try:
                            error_json = json.loads(error_body)
                        except:
                            pass
                except:
                    pass
            
            # Extract error message from OpenRouter's response if available
            openrouter_error_message = None
            if error_json and "error" in error_json:
                error_obj = error_json["error"]
                if isinstance(error_obj, dict):
                    openrouter_error_message = error_obj.get("message", "")
                elif isinstance(error_obj, str):
                    openrouter_error_message = error_obj
            
            if status_code == 401:
                error_message = openrouter_error_message or "Authentication failed (401 Unauthorized). Please check your API key or credentials."
            elif status_code == 403:
                error_message = openrouter_error_message or "Access forbidden (403). Please check your API key permissions."
            elif status_code == 404:
                if openrouter_error_message:
                    error_message = openrouter_error_message
                else:
                    error_message = f"Endpoint not found (404). Please check the API URL and path configuration. Requested URL: {url}"
            else:
                error_message = openrouter_error_message or f"HTTP error {status_code}: {str(http_error)}"
            yield LLMEvent(type="error", error=error_message)
            
        except httpx.RequestError as request_error:
            error_message = f"Connection error: {str(request_error)}. Please check your network connection and API endpoint."
            yield LLMEvent(type="error", error=error_message)
            
        except Exception as e:
            yield LLMEvent(type="error", error=f"HTTP request failed: {str(e)}")
