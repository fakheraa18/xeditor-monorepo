# Unified LiteLLM Tool Calling Tests

Test all providers (LM Studio, Ollama, vLLM) using a single unified interface. Requires LiteLLM v1.63.0+ for full reasoning support.

## Setup

```bash
# Install LiteLLM
uv pip install litellm
```

## 💡 Key Learnings for LiteLLM

- **Ollama Prefix**: Use `ollama_chat/<model>` instead of `ollama/<model>` to enable native tool calling (routes to `/api/chat` instead of `/api/generate`).
- **Model Prefixes**: Always prefix model names with the provider (e.g., `openai/gpt-oss-20b` for LM Studio/vLLM).
- **Reasoning Support**: Use `include_reasoning=True` in the completion call. LiteLLM v1.63.0+ standardizes this in `reasoning_content` and `thinking_blocks`.
- **Nested Model IDs**: For vLLM, if the model is registered as `openai/gpt-oss-20b`, the LiteLLM ID becomes `openai/openai/gpt-oss-20b`.

## Usage

```bash
# Activate virtual environment
source .venv/bin/activate

# List available providers
python litellm_tool_test.py --list

# Test all available providers (one at a time, VRAM-aware)
python litellm_tool_test.py --all

# Test specific provider
python litellm_tool_test.py lm-studio
python litellm_tool_test.py ollama
python litellm_tool_test.py vllm
```

## Comprehensive Test Script

```bash
# Test all available providers automatically
source .venv/bin/activate && ./test_litellm_all.sh
```

The tests will check if the model:
- ✅ Properly calls tools when needed
- ✅ Shows thinking/reasoning in the response (via `reasoning_content` or tag parsing)
- ✅ Provides main content response

## Important Note (Ollama + LiteLLM + tools)

Tool calling works via LiteLLM **only** when using the `ollama_chat/<model>` prefix (routes to Ollama `POST /api/chat`). If you use `ollama/<model>` LiteLLM routes to `POST /api/generate`, which will not preserve `tool_calls` the same way.

## Native Provider Tests (No LiteLLM)

If you prefer testing providers directly without the LiteLLM abstraction:

### LM Studio
```bash
python tool_test.py
# OR
./test_tool_calling.sh
```

### Ollama
```bash
python ollama_tool_test.py
# OR
./ollama_curl_test.sh
```

### vLLM
```bash
# Set your API key if needed
BASE_URL=http://localhost:8000/v1 API_KEY=your-key python tool_test.py
```

## Refs
- LiteLLM Ollama docs: `https://docs.litellm.ai/docs/providers/ollama`
- LiteLLM Reasoning docs: `https://docs.litellm.ai/docs/reasoning_content`
