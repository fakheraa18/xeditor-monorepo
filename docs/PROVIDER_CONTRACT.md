# Provider Output Contract

This document describes the contract that all LLM providers must follow to ensure compatibility with XEditor's agent prompt sets and parsers.

## Overview

All providers must emit responses in a standardized format that works with our existing prompt templates and response parsers. This ensures that switching between providers (OpenAI, Ollama, LM Studio, etc.) doesn't require changing prompts or parsers.

## Event Contract

Providers emit events via `LLMEvent` objects with the following types:

### 1. Thinking Events

**Type:** `"thinking"`  
**Purpose:** Internal reasoning/reasoning that should be displayed separately from main content

**Format:**
```python
LLMEvent(type="thinking", content="<reasoning text>")
```

**Behavior:**
- Emitted as chunks during streaming
- Displayed in UI as collapsible "Thinking" sections
- **Never** sent back to the LLM in subsequent requests (meta-only)
- Extracted from provider-specific formats:
  - Ollama: `message.thinking` field
  - LM Studio: `reasoning` output type
  - Others: Provider-specific reasoning fields

### 2. Content Events

**Type:** `"content"`  
**Purpose:** Main response content (user-visible text)

**Format:**
```python
LLMEvent(type="content", content="<content text>")
```

**Behavior:**
- Emitted as chunks during streaming
- Contains user-visible text only
- Tool calls should **not** be embedded here (use `tool_call` events instead)
- May contain Harmony tokens or JSON-in-text as a **fallback** for models that don't support structured tool calls
- Final content (after tool calls are stripped by parser) is displayed to the user

### 3. Tool Call Events

**Type:** `"tool_call"`  
**Purpose:** Structured tool calls (preferred over text-based tool calls)

**Format:**
```python
LLMEvent(
    type="tool_call",
    tool_call={
        "tool": "read_file",
        "args": {"path": "frontend/README.md"}
    }
)
```

**Behavior:**
- Emitted when provider detects native tool calls (e.g., Ollama `message.tool_calls`, OpenAI `delta.tool_calls`)
- **Preferred path** for providers that support native tool calling
- Agent runner handles these directly without requiring parser extraction
- If provider doesn't support native tool calls, fall back to Harmony tokens in `content` events

### 4. End Event

**Type:** `"end"`  
**Purpose:** Signals completion of the stream

**Format:**
```python
LLMEvent(
    type="end",
    usage={"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
    finish_reason="stop"
)
```

### 5. Error Event

**Type:** `"error"`  
**Purpose:** Signals an error occurred

**Format:**
```python
LLMEvent(type="error", error="<error message>")
```

## Tool Call Contract

### Preferred: Structured Tool Call Events

Providers that support native tool calling (e.g., Ollama `message.tool_calls`, OpenAI `delta.tool_calls`) should emit structured `tool_call` events:

```python
# When provider detects native tool call
yield LLMEvent(
    type="tool_call",
    tool_call={
        "tool": "read_file",
        "args": {"path": "frontend/README.md"}
    }
)
```

**Benefits:**
- More reliable than parsing text
- Works across all providers that support native tool calling
- No dependency on prompt-set-specific text formats
- Agent runner handles these directly

### Fallback: Harmony Tokens in Content

For providers/models that don't support native tool calling, tool calls can be embedded as **Harmony tokens** in `content` events. This is a fallback path that works with text-based models.

**Format:**
```
<|channel|>commentary to=<tool_name> <|constrain|>json<|message|>{<json_args>}
```

**Example:**
```
<|channel|>commentary to=read_file <|constrain|>json<|message|>{"target_file":"frontend/README.md"}
```

**When to use:**
- Model doesn't support native tool calling APIs
- Community prompt sets that instruct models to output Harmony tokens
- Backward compatibility with existing prompt sets

### Provider Responsibilities

1. **Prefer structured tool_call events** when provider supports native tool calling
   - Emit `LLMEvent(type="tool_call", tool_call={...})` for native tool calls
   - This is the preferred path for providers like Ollama, OpenAI, Anthropic, etc.

2. **Fallback to Harmony tokens** for text-only models
   - If provider doesn't support native tool calling, rely on prompt sets to generate Harmony tokens
   - Emit Harmony tokens as `content` events
   - Parsers will extract tool calls from content

3. **Do NOT send provider-native tool calling parameters** (optional)
   - Some providers allow disabling native tool calling to force text-based tool calls
   - Stripping `tools` parameter ensures models generate Harmony tokens instead
   - This is provider-specific and optional

4. **Never emit `<tool_code>` tags**
   - The old `<tool_code>{...}</tool_code>` format is deprecated
   - Use either structured `tool_call` events or Harmony format: `<|channel|>commentary to=...`

## Example Provider Implementation

### Provider with Native Tool Calling Support

```python
async def stream(self, request: LLMRequest) -> AsyncGenerator[LLMEvent, None]:
    # 1. Optional: Strip 'tools' from request to force text-based tool calling
    # (Only if you want to disable native tool calling)
    filtered_payload = {k: v for k, v in request.extra_payload.items() if k != "tools"}
    
    # 2. Make request to provider API
    async for chunk in provider_api_stream(filtered_payload):
        # 3. Extract thinking (if present)
        if chunk.get("thinking"):
            yield LLMEvent(type="thinking", content=chunk["thinking"])
        
        # 4. Extract content
        if chunk.get("content"):
            yield LLMEvent(type="content", content=chunk["content"])
        
        # 5. Emit structured tool_call events for native tool calls (preferred)
        if chunk.get("tool_calls"):
            for call in chunk["tool_calls"]:
                fn = call.get("function", {})
                name = fn.get("name")
                args = fn.get("arguments", {})
                if isinstance(args, str):
                    try:
                        args = json.loads(args)
                    except:
                        args = {"raw": args}
                
                if name:
                    yield LLMEvent(
                        type="tool_call",
                        tool_call={
                            "tool": name,
                            "args": args,
                        }
                    )
    
    # 6. Emit end event
    yield LLMEvent(type="end", usage=usage, finish_reason="stop")
```

### Provider without Native Tool Calling Support

```python
async def stream(self, request: LLMRequest) -> AsyncGenerator[LLMEvent, None]:
    # Provider that only supports text-based tool calling
    async for chunk in provider_api_stream(request.extra_payload):
        if chunk.get("thinking"):
            yield LLMEvent(type="thinking", content=chunk["thinking"])
        
        if chunk.get("content"):
            # Content may contain Harmony tokens - parser will extract them
            yield LLMEvent(type="content", content=chunk["content"])
    
    yield LLMEvent(type="end", usage=usage, finish_reason="stop")
```

## Parser Contract

Parsers (like `HarmonyParser`) are responsible for extracting structured data from `content` events:

1. **Thinking tags** (optional): `<think>...</think>`
   - Extracted and displayed separately
   - Stripped from final content
   - **Note**: Prefer structured `thinking` events from providers when available

2. **Harmony tool calls** (optional): `<|channel|>commentary to=...`
   - Parsed and executed (fallback path)
   - Stripped from final content
   - **Note**: Structured `tool_call` events bypass parser - they're handled directly by agent runner

3. **Patch blocks** (optional): `<patch file="...">...</patch>`
   - Rendered as diff previews
   - Stripped from final content

4. **Final text**: Everything else after tags are stripped

**Important**: Parsers are only needed for the **fallback path** (text-based tool calls). When providers emit structured `tool_call` events, parsers are bypassed entirely.

## Benefits

- **Provider-agnostic prompt sets**: Prompt sets work across providers without provider-specific code
- **Flexible tool calling**: Supports both native tool calling (preferred) and text-based tool calling (fallback)
- **Easy provider switching**: Change provider without changing prompts/parsers
- **Community contributions**: Clear contract for adding new providers
- **Backward compatible**: Existing Harmony-based prompt sets continue to work

## References

- Prompt template: `server/prompt_sets/default/gpt/agent/prompt.py`
- Parser implementation: `server/prompt_sets/default/gpt/agent/parser.py`
- Provider examples: `server/providers/ollama.py`, `server/providers/lmstudio.py`
