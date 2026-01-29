"""
Ollama provider for direct API integration.

This provider directly calls Ollama's native API endpoints, providing
better control and debugging capabilities compared to using LiteLLM.
"""

import json
import logging
from typing import AsyncGenerator, Dict, Any, Optional

import httpx

from .base import LLMProvider
from .events import LLMEvent, LLMRequest, LLMResponse

# Set up logger for debugging
logger = logging.getLogger(__name__)

# Configure logging if not already configured
if not logging.root.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

# Set debug level for Ollama provider specifically
logger.setLevel(logging.DEBUG)


class OllamaProvider(LLMProvider):
    """
    Provider for Ollama models using native API.
    
    Supports:
    - Streaming chat completions (/api/chat)
    - Non-streaming chat completions
    - Tool calling (if supported by model)
    - Thinking models (extracts thinking from response)
    """
    
    async def stream(self, request: LLMRequest) -> AsyncGenerator[LLMEvent, None]:
        """Stream response from Ollama API."""
        base_url = self.get_base_url() or "http://localhost:11434"
        path = self.get_path() or "/api/chat"
        
        # Build full URL
        url = f"{base_url.rstrip('/')}{path}"
        
        # Build headers
        headers = self.get_headers()
        headers, url = self.apply_auth(headers, url)
        
        # Convert messages to Ollama format
        ollama_messages = self._convert_messages(request.messages)
        
        # Build request body according to Ollama API spec
        request_body: Dict[str, Any] = {
            "model": request.model_id,
            "messages": ollama_messages,
            "stream": True,
        }
        
        # Add temperature if provided
        if request.temperature is not None:
            request_body["options"] = request_body.get("options", {})
            request_body["options"]["temperature"] = request.temperature
        
        # Add max_tokens as num_predict in Ollama
        if request.max_tokens:
            request_body.setdefault("options", {})
            request_body["options"]["num_predict"] = request.max_tokens
        
        # Merge extra payload (for options, format, etc.)
        # CRITICAL: Strip 'tools' to enforce Harmony-only tool calling (our parser expects Harmony tokens)
        if request.extra_payload:
            filtered_payload = {k: v for k, v in request.extra_payload.items() if k != "tools"}
            if "options" in filtered_payload:
                request_body.setdefault("options", {}).update(filtered_payload["options"])
            else:
                request_body.update(filtered_payload)
        
        # Debug logging
        # logger.info(f"[Ollama] Request URL: {url}")
        # logger.info(f"[Ollama] Request headers: {json.dumps({k: v for k, v in headers.items() if k.lower() != 'authorization'}, indent=2)}")
        # logger.info(f"[Ollama] Request body: {json.dumps(request_body, indent=2)}")
        
        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                async with client.stream("POST", url, json=request_body, headers=headers) as response:
                    # Log response status
                    # logger.info(f"[Ollama] Response status: {response.status_code}")
                    
                    response.raise_for_status()
                    
                    full_content = ""
                    thinking_content = ""
                    finish_reason = None
                    usage = None
                    done_reason = None
                    
                    async for line in response.aiter_lines():
                        if not line.strip():
                            continue
                        
                        # Log raw response line
                        # logger.debug(f"[Ollama] Raw response line: {line[:200]}")  # Limit log length
                        
                        try:
                            data = json.loads(line)
                            
                            # Log parsed response
                            # logger.debug(f"[Ollama] Parsed response: {json.dumps(data, indent=2)}")
                            
                            # Extract message content
                            if "message" in data:
                                message = data["message"]
                                
                                # Extract thinking (for thinking models) - only if enabled in provider_params
                                thinking_enabled = request.provider_params.get("thinking", {}).get("enabled", False)
                                if "thinking" in message and thinking_enabled:
                                    thinking_chunk = message["thinking"]
                                    if thinking_chunk:
                                        thinking_content += thinking_chunk
                                        yield LLMEvent(type="thinking", content=thinking_chunk)
                                
                                # Extract content
                                if "content" in message:
                                    content_chunk = message["content"]
                                    if content_chunk:
                                        full_content += content_chunk
                                        yield LLMEvent(type="content", content=content_chunk)
                                
                                # Emit structured tool_call events for native tool calls (preferred path)
                                # Even though we don't send 'tools', some models might still return tool_calls.
                                # Emit as structured events so the agent runner can handle them directly.
                                tool_calls = message.get("tool_calls") if isinstance(message, dict) else None
                                if isinstance(tool_calls, list) and tool_calls:
                                    for call in tool_calls:
                                        if not isinstance(call, dict):
                                            continue
                                        fn = call.get("function") or {}
                                        if not isinstance(fn, dict):
                                            continue
                                        name = fn.get("name")
                                        args = fn.get("arguments") or {}
                                        if isinstance(args, str):
                                            # Some providers serialize arguments as a JSON string
                                            try:
                                                args = json.loads(args)
                                            except Exception:
                                                args = {"raw": args}
                                        if isinstance(name, str) and name:
                                            # Emit structured tool_call event (preferred over Harmony text)
                                            yield LLMEvent(
                                                type="tool_call",
                                                tool_call={
                                                    "tool": name,
                                                    "args": args,
                                                }
                                            )
                            else:
                                # Fallback: /api/generate-style streaming (top-level fields)
                                thinking_enabled = request.provider_params.get("thinking", {}).get("enabled", False)
                                thinking_chunk = data.get("thinking")
                                if thinking_chunk and thinking_enabled:
                                    thinking_content += str(thinking_chunk)
                                    yield LLMEvent(type="thinking", content=str(thinking_chunk))
                                
                                response_chunk = data.get("response") or data.get("content")
                                if response_chunk:
                                    full_content += str(response_chunk)
                                    yield LLMEvent(type="content", content=str(response_chunk))
                            
                            # Check if done
                            if data.get("done", False):
                                done_reason = data.get("done_reason")
                                finish_reason = done_reason or "stop"
                                
                                # Extract usage statistics
                                if "prompt_eval_count" in data or "eval_count" in data:
                                    usage = {
                                        "prompt_tokens": data.get("prompt_eval_count", 0),
                                        "completion_tokens": data.get("eval_count", 0),
                                        "total_tokens": (
                                            data.get("prompt_eval_count", 0) + 
                                            data.get("eval_count", 0)
                                        ),
                                    }
                                
                                # Log final statistics
                                logger.info(f"[Ollama] Stream complete. Content length: {len(full_content)}, "
                                          f"Thinking length: {len(thinking_content)}, "
                                          f"Usage: {usage}, Done reason: {done_reason}")
                                
                                break
                                
                        except json.JSONDecodeError as e:
                            logger.warning(f"[Ollama] Failed to parse JSON line: {line[:100]} - {e}")
                            continue
                    
                    # Yield end event
                    yield LLMEvent(
                        type="end",
                        usage=usage,
                        finish_reason=finish_reason,
                    )
                    
        except httpx.HTTPStatusError as http_error:
            status_code = http_error.response.status_code
            error_body = ""
            try:
                error_body = http_error.response.text
                logger.error(f"[Ollama] HTTP {status_code} error: {error_body}")
            except:
                logger.error(f"[Ollama] HTTP {status_code} error: {str(http_error)}")
            
            if status_code == 401:
                error_message = "Authentication failed (401 Unauthorized). Please check your Ollama configuration."
            elif status_code == 404:
                error_message = f"Model or endpoint not found (404). Check if model '{request.model_id}' exists and endpoint '{url}' is correct."
            elif status_code == 500:
                error_message = f"Ollama server error (500): {error_body[:200] if error_body else 'Internal server error'}"
            else:
                error_message = f"HTTP error {status_code}: {error_body[:200] if error_body else str(http_error)}"
            
            yield LLMEvent(type="error", error=error_message)
            
        except httpx.RequestError as request_error:
            logger.error(f"[Ollama] Connection error: {str(request_error)}")
            error_message = f"Connection error: {str(request_error)}. Is Ollama running at {base_url}?"
            yield LLMEvent(type="error", error=error_message)
            
        except Exception as e:
            logger.exception(f"[Ollama] Unexpected error: {str(e)}")
            yield LLMEvent(type="error", error=f"Ollama request failed: {str(e)}")
    
    def _convert_messages(self, messages: list) -> list:
        """
        Convert messages to Ollama format.
        
        Ollama expects messages with 'role' and 'content' fields.
        Supports: system, user, assistant, tool
        """
        ollama_messages = []
        
        for msg in messages:
            if isinstance(msg, dict):
                role = msg.get("role", "user")
                content = msg.get("content", "")
                
                ollama_msg: Dict[str, Any] = {
                    "role": role,
                    "content": content,
                }
                
                # Handle images (for multimodal models)
                if "images" in msg and msg["images"]:
                    ollama_msg["images"] = msg["images"]
                
                # Handle tool calls
                if "tool_calls" in msg and msg["tool_calls"]:
                    ollama_msg["tool_calls"] = msg["tool_calls"]
                
                # Handle tool results
                if role == "tool" and "tool_name" in msg:
                    ollama_msg["tool_name"] = msg["tool_name"]
                
                ollama_messages.append(ollama_msg)
            else:
                # Fallback for non-dict messages
                ollama_messages.append({
                    "role": "user",
                    "content": str(msg),
                })
        
        return ollama_messages
    
    async def chat(self, request: LLMRequest) -> "LLMResponse":
        """
        Non-streaming chat completion.
        
        Override to use Ollama's non-streaming mode for better performance.
        """
        base_url = self.get_base_url() or "http://localhost:11434"
        path = self.get_path() or "/api/chat"
        url = f"{base_url.rstrip('/')}{path}"
        
        headers = self.get_headers()
        headers, url = self.apply_auth(headers, url)
        
        ollama_messages = self._convert_messages(request.messages)
        
        request_body: Dict[str, Any] = {
            "model": request.model_id,
            "messages": ollama_messages,
            "stream": False,  # Non-streaming
        }
        
        if request.temperature is not None:
            request_body.setdefault("options", {})
            request_body["options"]["temperature"] = request.temperature
        
        if request.max_tokens:
            request_body.setdefault("options", {})
            request_body["options"]["num_predict"] = request.max_tokens
        
        # CRITICAL: Strip 'tools' to enforce Harmony-only tool calling (our parser expects Harmony tokens)
        if request.extra_payload:
            filtered_payload = {k: v for k, v in request.extra_payload.items() if k != "tools"}
            if "options" in filtered_payload:
                request_body.setdefault("options", {}).update(filtered_payload["options"])
            else:
                request_body.update(filtered_payload)
        
        # logger.info(f"[Ollama] Non-streaming request to {url}")
        # logger.debug(f"[Ollama] Request body: {json.dumps(request_body, indent=2)}")
        
        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                response = await client.post(url, json=request_body, headers=headers)
                response.raise_for_status()
                
                data = response.json()
                # logger.info(f"[Ollama] Response: {json.dumps(data, indent=2)}")
                
                message = data.get("message", {})
                content = message.get("content", "")
                # Only extract thinking if enabled in provider_params
                thinking_enabled = request.provider_params.get("thinking", {}).get("enabled", False)
                thinking = message.get("thinking", "") if thinking_enabled else ""
                
                # Defensive fallback: translate native tool_calls to Harmony format
                # Even though we don't send 'tools', some models might still return tool_calls.
                # Convert to Harmony format so HarmonyParser can parse it.
                tool_calls = message.get("tool_calls") if isinstance(message, dict) else None
                if isinstance(tool_calls, list) and tool_calls:
                    harmony_parts: list[str] = []
                    for call in tool_calls:
                        if not isinstance(call, dict):
                            continue
                        fn = call.get("function") or {}
                        if not isinstance(fn, dict):
                            continue
                        name = fn.get("name")
                        args = fn.get("arguments") or {}
                        if isinstance(args, str):
                            try:
                                args = json.loads(args)
                            except Exception:
                                args = {"raw": args}
                        if isinstance(name, str) and name:
                            # Convert to Harmony format: <|channel|>commentary to=<tool_name> <|constrain|>json<|message|>{...}
                            harmony_parts.append(
                                f"<|channel|>commentary to={name} <|constrain|>json<|message|>{json.dumps(args)}"
                            )
                    if harmony_parts:
                        content = "".join(harmony_parts) + (content if content else "")
                
                # Fallback: /api/generate-style response fields
                if not content and isinstance(data, dict) and (data.get("response") or data.get("content")):
                    content = str(data.get("response") or data.get("content") or "")
                if not thinking and thinking_enabled and isinstance(data, dict) and data.get("thinking"):
                    thinking = str(data.get("thinking") or "")
                
                usage = None
                if "prompt_eval_count" in data or "eval_count" in data:
                    usage = {
                        "prompt_tokens": data.get("prompt_eval_count", 0),
                        "completion_tokens": data.get("eval_count", 0),
                        "total_tokens": (
                            data.get("prompt_eval_count", 0) + 
                            data.get("eval_count", 0)
                        ),
                    }
                
                return LLMResponse(
                    content=content,
                    thinking=thinking if thinking else None,
                    usage=usage,
                    finish_reason=data.get("done_reason", "stop"),
                )
                
        except Exception as e:
            logger.exception(f"[Ollama] Non-streaming request failed: {str(e)}")
            return LLMResponse(
                content="",
                error=f"Ollama request failed: {str(e)}",
            )
