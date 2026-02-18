"""
Unified LiteLLM provider for all model routing.

Routes all requests through LiteLLM with runtime model prefix normalization.
Handles tools, thinking/reasoning, usage, and tool_calls from LiteLLM responses.
"""

import json
import uuid
from typing import AsyncGenerator, Dict, Any, Optional

import litellm

from .base import LLMProvider
from .events import LLMEvent, LLMRequest, TokenUsage
from .normalize import (
    normalize_model_name,
    build_litellm_kwargs_from_connection,
)


class LiteLLMProvider(LLMProvider):
    """
    Unified provider for all models via LiteLLM.

    Uses provider prefix + model_id for routing. Supports:
    - All LiteLLM providers (openai, anthropic, ollama, lm_studio, etc.)
    - OpenAI-compatible endpoints (openai/ with api_base)
    - local_companion/vllm (routes to vllm_manager)
    - Native tool_calls, reasoning_content, and usage
    """

    async def stream(self, request: LLMRequest) -> AsyncGenerator[LLMEvent, None]:
        """Stream response using LiteLLM."""
        provider = request.provider or self.config.get("provider", "")
        model_id = request.model_id or ""
        connection = request.connection or self.connection
        auth = request.auth or self.auth

        # Build LiteLLM kwargs from connection/auth first to get api_base
        conn_kwargs = build_litellm_kwargs_from_connection(
            provider,
            connection,
            auth,
            local_companion=self.config.get("localCompanion"),
        )

        # Normalize model name - pass api_base so it knows to skip prefix for custom endpoints
        litellm_model = normalize_model_name(
            provider,
            model_id,
            family=request.family,
            base_url=connection.get("baseUrl"),
            api_base=conn_kwargs.get("api_base"),
        )

        if not litellm_model:
            yield LLMEvent(
                type="error",
                error="Invalid model configuration: provider and model ID are required.",
            )
            return

        litellm_kwargs: Dict[str, Any] = {
            "model": litellm_model,
            "messages": request.messages,
            "temperature": request.temperature,
            "stream": True,
            "stream_options": {"include_usage": True},  # Request usage in final stream chunk
            **conn_kwargs,
        }

        if request.max_tokens:
            litellm_kwargs["max_tokens"] = request.max_tokens

        if request.tools:
            litellm_kwargs["tools"] = request.tools
            litellm_kwargs["tool_choice"] = request.tool_choice

        if request.extra_payload:
            litellm_kwargs.update(request.extra_payload)

        try:
            finish_reason = None
            usage = None
            tool_calls_acc: Dict[int, Dict[str, Any]] = {}

            response = await litellm.acompletion(**litellm_kwargs)

            async for chunk in response:
                if not hasattr(chunk, "choices") or not chunk.choices:
                    continue

                choice = chunk.choices[0]
                delta = getattr(choice, "delta", None)
                if not delta:
                    continue

                # Content
                if hasattr(delta, "content") and delta.content:
                    yield LLMEvent(type="content", content=delta.content)

                # Reasoning/thinking (LiteLLM standardized)
                if hasattr(delta, "reasoning_content") and delta.reasoning_content:
                    yield LLMEvent(type="thinking", content=delta.reasoning_content)

                # Tool calls (streaming) - accumulate by index
                tcs = getattr(delta, "tool_calls", None) or []
                for tc in tcs:
                    tc_dict = tc if isinstance(tc, dict) else None
                    if tc_dict is None and hasattr(tc, "__dict__"):
                        tc_dict = {
                            "index": getattr(tc, "index", None),
                            "id": getattr(tc, "id", None),
                            "function": getattr(tc, "function", None),
                        }
                    if not tc_dict:
                        continue
                    idx = tc_dict.get("index")
                    if idx is None:
                        continue
                    fn = tc_dict.get("function")
                    if fn is not None and not isinstance(fn, dict) and hasattr(fn, "name"):
                        fn = {"name": getattr(fn, "name", None), "arguments": getattr(fn, "arguments", None) or ""}
                    fn = fn or {}
                    if idx not in tool_calls_acc:
                        tool_calls_acc[idx] = {"name": "", "arguments": "", "id": tc_dict.get("id", ""), "emitted": False}
                    acc = tool_calls_acc[idx]
                    if acc.get("emitted"):
                        continue
                    if fn.get("name"):
                        acc["name"] = fn["name"]
                    if fn.get("arguments") is not None:
                        acc["arguments"] = acc.get("arguments", "") + str(fn["arguments"])
                    if tc_dict.get("id"):
                        acc["id"] = tc_dict["id"]
                    name = acc.get("name", "")
                    args_str = acc.get("arguments", "")
                    if name and args_str:
                        try:
                            args = json.loads(args_str)
                            tool_call_id = acc.get("id") or f"call_{idx}_{uuid.uuid4().hex[:8]}"
                            yield LLMEvent(
                                type="tool_call",
                                tool_call={"tool": name, "args": args, "id": tool_call_id},
                            )
                            acc["emitted"] = True
                        except json.JSONDecodeError:
                            pass

                if hasattr(choice, "finish_reason") and choice.finish_reason:
                    finish_reason = choice.finish_reason

                if hasattr(chunk, "usage") and chunk.usage:
                    usage = self._usage_from_chunk(chunk.usage)

            yield LLMEvent(
                type="end",
                usage=usage,
                finish_reason=finish_reason,
            )

        except Exception as e:
            error_str = str(e)
            error_lower = error_str.lower()
            is_auth_error = (
                "api_key" in error_lower
                or "api key" in error_lower
                or "authentication" in error_lower
                or "unauthorized" in error_lower
                or "invalid api" in error_lower
            )
            if is_auth_error:
                api_key_provided = auth.get("type") == "bearer" and auth.get("apiKey")
                if not api_key_provided:
                    error_message = f"API key is required. Please configure your API key in the model settings."
                else:
                    error_message = f"Authentication failed: {error_str}"
            else:
                error_message = f"LiteLLM error: {error_str}"
            yield LLMEvent(type="error", error=error_message)

    def _usage_from_chunk(self, usage: Any) -> Optional[Dict[str, Any]]:
        """
        Extract usage dict from LiteLLM chunk.usage.
        Handles OpenAI-style, Anthropic, Gemini, LMStudio, and other LiteLLM variants.
        """
        if not usage:
            return None

        # Already a dict (e.g. from some providers)
        if isinstance(usage, dict):
            parsed = TokenUsage.from_auto(usage)
            return parsed.to_dict() if parsed else None

        # Object with attributes
        result: Dict[str, Any] = {
            "prompt_tokens": getattr(usage, "prompt_tokens", 0) or 0,
            "completion_tokens": getattr(usage, "completion_tokens", 0) or 0,
            "total_tokens": getattr(usage, "total_tokens", 0) or 0,
        }

        # completion_tokens_details - reasoning_tokens (OpenAI o1, Anthropic extended thinking)
        details = getattr(usage, "completion_tokens_details", None)
        if details:
            if isinstance(details, dict):
                reasoning = details.get("reasoning_tokens")
                if reasoning is not None:
                    result["reasoning_tokens"] = reasoning
            elif hasattr(details, "reasoning_tokens") and details.reasoning_tokens is not None:
                result["reasoning_tokens"] = details.reasoning_tokens

        # input_tokens_details - cached_tokens
        input_details = getattr(usage, "input_tokens_details", None)
        if input_details:
            if isinstance(input_details, dict):
                cached = input_details.get("cached_tokens")
                if cached is not None:
                    result["cached_tokens"] = cached
            elif hasattr(input_details, "cached_tokens") and input_details.cached_tokens is not None:
                result["cached_tokens"] = input_details.cached_tokens

        # Ensure total_tokens if missing
        if not result["total_tokens"] and (result["prompt_tokens"] or result["completion_tokens"]):
            result["total_tokens"] = result["prompt_tokens"] + result["completion_tokens"]

        return result
