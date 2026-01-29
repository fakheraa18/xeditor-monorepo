"""
Google Gemini provider.

Handles the Gemini-specific API format and authentication.
Supports both Google AI Studio (generativelanguage.googleapis.com) and Vertex AI endpoints.
"""

import json
from typing import AsyncGenerator, Dict, Any, List
from urllib.parse import urlparse

import httpx

from .base import LLMProvider
from .events import LLMEvent, LLMRequest


def is_gemini_endpoint(base_url: str, path: str = "") -> bool:
    """Check if this is a Google Generative Language (Gemini) endpoint."""
    if not base_url:
        return False
    try:
        parsed = urlparse(base_url)
        host = parsed.netloc.lower()
        if "generativelanguage.googleapis.com" in host:
            return True
        if path and (":generateContent" in path or ":streamGenerateContent" in path):
            return True
    except Exception:
        pass
    return False


def convert_messages_to_gemini_format(messages: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Convert OpenAI-style messages to Gemini API format."""
    contents = []
    system_instruction = None
    
    for msg in messages:
        role = msg.get("role", "").lower()
        content = msg.get("content", "")
        
        if role == "system":
            # Gemini uses systemInstruction for system messages
            if not system_instruction:
                system_instruction = content
            else:
                # Combine multiple system messages
                system_instruction += "\n\n" + content
        elif role == "user":
            contents.append({
                "role": "user",
                "parts": [{"text": content}]
            })
        elif role == "assistant":
            contents.append({
                "role": "model",
                "parts": [{"text": content}]
            })
    
    result: Dict[str, Any] = {"contents": contents}
    if system_instruction:
        result["systemInstruction"] = {"parts": [{"text": system_instruction}]}
    
    return result


class GeminiProvider(LLMProvider):
    """
    Provider for Google Gemini models.
    
    Uses the Gemini REST API. Supports multiple authentication methods:
    - Google AI Studio: Custom header (x-goog-api-key)
    - Vertex AI: Bearer token or other auth methods
    
    Handles thinking configuration for Gemini-3 models:
    - Validates that thinking config is properly nested under generationConfig.thinkingConfig
    - Rejects invalid top-level thinking fields with helpful error messages
    """
    
    async def stream(self, request: LLMRequest) -> AsyncGenerator[LLMEvent, None]:
        """Stream response from Gemini API."""
        base_url = self.get_base_url()
        path = self.get_path()
        
        # Build streaming URL
        if ":generateContent" in path:
            stream_path = path.replace(":generateContent", ":streamGenerateContent") + "?alt=sse"
        elif ":streamGenerateContent" in path:
            stream_path = path + "?alt=sse" if "?alt=sse" not in path else path
        else:
            stream_path = path + ":streamGenerateContent?alt=sse"
        
        url = self.build_url(stream_path)
        
        # Build headers and apply auth (supports both AI Studio and Vertex AI)
        headers = self.get_headers()
        headers, url = self.apply_auth(headers, url)
        
        # Convert messages to Gemini format
        gemini_body = convert_messages_to_gemini_format(request.messages)
        
        # Build generation config from request parameters
        generation_config: Dict[str, Any] = {}
        if request.temperature is not None:
            generation_config["temperature"] = request.temperature
        if request.max_tokens:
            generation_config["maxOutputTokens"] = request.max_tokens
        
        # Process extra_payload: validate thinking config and merge generationConfig
        if request.extra_payload:
            # Check for invalid top-level thinking fields
            thinking_fields = ["thinking_level", "thinkingLevel", "thinking_config", "thinkingConfig"]
            invalid_thinking = [k for k in thinking_fields if k in request.extra_payload]
            
            if invalid_thinking:
                yield LLMEvent(
                    type="error",
                    error=(
                        f"Invalid thinking configuration: {', '.join(invalid_thinking)} found at top level. "
                        "For Gemini-3 models, thinking must be configured as: "
                        'extraPayload: { "generationConfig": { "thinkingConfig": { "thinkingLevel": "low" } } }. '
                        "Accepted values for gemini-3-flash-preview: minimal, low, medium, high. "
                        "Accepted values for gemini-3-pro: low, high."
                    )
                )
                return
            
            # Deep-merge generationConfig from extra_payload
            if "generationConfig" in request.extra_payload:
                extra_gen_config = request.extra_payload["generationConfig"]
                if isinstance(extra_gen_config, dict):
                    # Deep merge: extra_payload values override defaults
                    generation_config.update(extra_gen_config)
            
            # Merge remaining top-level fields (safetySettings, tools, etc.)
            # Exclude generationConfig since we already merged it
            remaining_payload = {
                k: v for k, v in request.extra_payload.items()
                if k != "generationConfig"
            }
            gemini_body.update(remaining_payload)
        
        # Set generationConfig if we have any config
        if generation_config:
            gemini_body["generationConfig"] = generation_config
        
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                async with client.stream("POST", url, json=gemini_body, headers=headers) as response:
                    response.raise_for_status()
                    
                    full_content = ""
                    finish_reason = None
                    usage = None
                    
                    async for line in response.aiter_lines():
                        if not line.strip():
                            continue
                        
                        # Gemini SSE format: "data: {json}"
                        if line.startswith("data: "):
                            data_str = line[6:].strip()
                            if data_str == "[DONE]":
                                break
                            
                            try:
                                data = json.loads(data_str)
                                
                                # Parse Gemini streaming response
                                if "candidates" in data and len(data["candidates"]) > 0:
                                    candidate = data["candidates"][0]
                                    
                                    if "content" in candidate and "parts" in candidate["content"]:
                                        parts = candidate["content"]["parts"]
                                        for part in parts:
                                            if "text" in part:
                                                chunk = part["text"]
                                                full_content += chunk
                                                yield LLMEvent(type="content", content=chunk)
                                    
                                    if "finishReason" in candidate:
                                        fr = candidate["finishReason"].lower()
                                        if fr == "stop":
                                            finish_reason = "stop"
                                        elif fr == "max_tokens":
                                            finish_reason = "length"
                                        elif fr == "safety":
                                            finish_reason = "content_filter"
                                        else:
                                            finish_reason = "stop"
                                
                                if "usageMetadata" in data:
                                    usage_meta = data["usageMetadata"]
                                    usage = {
                                        "prompt_tokens": usage_meta.get("promptTokenCount", 0),
                                        "completion_tokens": usage_meta.get("candidatesTokenCount", 0),
                                        "total_tokens": usage_meta.get("totalTokenCount", 0),
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
            error_body = ""
            try:
                error_body = http_error.response.text
            except:
                pass
            
            if status_code == 400:
                # Include response body for 400s to help debug configuration issues
                error_preview = error_body[:300] if error_body else ""
                error_message = (
                    f"Bad request (400). Please check your request configuration. "
                    f"{'Response: ' + error_preview + ('...' if len(error_body or '') > 300 else '') if error_preview else ''}"
                )
            elif status_code == 401:
                error_message = (
                    "Authentication failed (401 Unauthorized). Please check your Gemini API key. "
                    "Ensure authentication is properly configured in the model settings."
                )
            elif status_code == 403:
                error_message = "Access forbidden (403). Please check your API key permissions."
            elif status_code == 404:
                error_message = "Endpoint not found (404). Please check the API URL and path configuration."
            else:
                error_preview = error_body[:200] if error_body else ""
                error_message = (
                    f"HTTP error {status_code}: {str(http_error)}"
                    f"{'. Response: ' + error_preview if error_preview else ''}"
                )
            yield LLMEvent(type="error", error=error_message)
            
        except httpx.RequestError as request_error:
            error_message = f"Connection error: {str(request_error)}. Please check your network connection and API endpoint."
            yield LLMEvent(type="error", error=error_message)
            
        except Exception as e:
            yield LLMEvent(type="error", error=f"Gemini streaming request failed: {str(e)}")
