# XEditor Local Companion

A local Python server that acts as a proxy and runtime for LLM inference, code indexing, and other heavy tasks from the XEditor web application.

## Architecture Overview

The Local Companion implements a **dual WebSocket architecture** that separates streaming operations from control operations, preventing interference between AI chat streaming and file system events.

```
┌─────────────────────────────────────────────────────────┐
│                    XEditor Web Application              │
├─────────────────────────────────────────────────────────┤
│  Chat Store ─────────streamRequest()────────┐           │
│                                             │           │
│  Project Store ──────request()──────────────┼───┐       │
│  Indexing Store ─────request()──────────────┼───┤       │
│  File Tree ──────────request()──────────────┼───┘       │
└─────────────────────────────────────────────┼───────────┘
                                              │
              ┌───────────────────────────────┼───────────┐
              │                               │           │
              ▼                               ▼           │
┌─────────────────────────┐   ┌─────────────────────────┐ │
│  /ws/stream             │   │  /ws/control            │ │
│  (Streaming Operations) │   │  (RPC Operations)       │ │
├─────────────────────────┤   ├─────────────────────────┤ │
│ • chat_message          │   │ • file operations       │ │
│ • llm_stream_request_v2 │   │ • indexing operations   │ │
│ • cancel                │   │ • project management    │ │
│ • stream_resume         │   │ • model/prompt config   │ │
│                         │   │ • file_changed events   │ │
└─────────────────────────┘   └─────────────────────────┘ │
              │                               │           │
              └───────────────────────────────┼───────────┘
                                              │
┌─────────────────────────────────────────────┼───────────┐
│            Local Companion Server           │           │
│                                             ▼           │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Stream Buffer (with sequence numbers)          │   │
│  │  • Buffers events for resumption support        │   │
│  │  • TTL-based cleanup of expired sessions        │   │
│  └─────────────────────────────────────────────────┘   │
│                                                         │
│  ┌─────────────────────────────────────────────────┐   │
│  │  Local Runtime Execution                        │   │
│  │  • Tree-sitter Parsing ──► JS/TS, Vue, Python   │   │
│  │  • Sentence-Transformers ──► Embeddings         │   │
│  │  • LLM Providers ──► OpenAI, Anthropic, Ollama  │   │
│  │  • vLLM Runtime (Optional, Linux + CUDA)        │   │
│  └─────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────┘
```

### Key Benefits

1. **Stream Isolation**: AI chat streaming is never interrupted by file tree refreshes or indexing operations
2. **Stream Resumption**: If a stream WebSocket disconnects, clients can resume from the last received event using sequence numbers
3. **Independent Reconnection**: Each WebSocket can reconnect independently without affecting the other

### Key Behaviors

1. **Companion-First Routing**: When the companion is connected, **all LLM requests** and **indexing tasks** are automatically routed through it.
2. **Fully Local Indexing**: Unlike standard proxies, the companion performs **AST parsing** and **vector embedding** entirely on your machine. No code or text is sent to external APIs for indexing.
3. **Automatic Fallback**: If the companion is unavailable or a request fails, the web app automatically falls back to direct browser-based adapters (Transformers.js for embeddings, Web Worker for parsing).
4. **Local Runtime Support**: Uses `light-embed` (ONNX-based) for embeddings and `tree-sitter` for high-fidelity code parsing.

## Setup

### Quick Start (Recommended)

1. **Install [uv](https://github.com/astral-sh/uv)** (Recommended)
2. **Run the server**:
   ```bash
   uv run python main.py --port 8000
   ```
   (This will automatically install dependencies including `tree-sitter-languages` and `light-embed`)
   
   **For GPU acceleration** (optional, requires CUDA-capable GPU):
   ```bash
   uv sync --extra gpu
   ```

### Manual Setup

1. **Install Python 3.12+**
2. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

## Local Indexing Features

### 1. Tree-sitter Parsing
The companion uses native `tree-sitter` for robust symbol extraction and AST-aware chunking.
- **Languages**: TypeScript (TSX), JavaScript (JSX), Vue SFC (script blocks), Python, Go, Rust, Java, C/C++, HTML, CSS, JSON.
- **Smart Chunking**: Chunks are created based on top-level declarations (functions, classes, interfaces) with surrounding context.

### 2. Local Embeddings
Uses `light-embed` (ONNX-based) to generate vectors locally.
- **Model Download**: Model weights/ONNX files are downloaded once from Hugging Face (no text/code is ever sent to HF).
- **GPU Acceleration**: 
  - **Development**: Install with `uv sync --extra gpu` to enable GPU acceleration via `onnxruntime-gpu` (requires CUDA-capable GPU).
  - **Packaged Builds**: GPU support is automatically included. The packaged app will use GPU if available, otherwise falls back to CPU automatically.
- **Gated Models**: Provide an optional Hugging Face token in the UI if you wish to use gated or private models.

## WebSocket Protocol

The companion uses a dual WebSocket architecture with two endpoints:

- **`/ws/stream`** - Dedicated to streaming operations (AI chat, LLM streaming)
- **`/ws/control`** - Handles all other RPC operations (file ops, indexing, config)

This separation ensures that file change events and indexing operations never interrupt active AI chat streaming.

### Message Format

**Request:**
```json
{
  "type": "<message_type>",
  "id": "<request_id>",
  "payload": { ... }
}
```

**Response (with sequence number for streaming):**
```json
{
  "type": "<response_type>",
  "id": "<request_id>",
  "seq": 42,
  "payload": { ... }
}
```

### Stream Resumption

If a stream connection is interrupted, clients can resume from where they left off:

```json
{
  "type": "stream_resume",
  "id": "<request_id>",
  "payload": {
    "streamId": "<original_stream_id>",
    "fromSeq": 42
  }
}
```

The server will replay all buffered events with sequence numbers greater than `fromSeq`.

### Supported RPC Endpoints

#### LLM Requests

**`llm_request_v2`** - Enriched LLM request with full provider/connection/auth info (single source of truth):
```json
{
  "type": "llm_request_v2",
  "id": "req_123",
  "payload": {
    "provider": "openai",
    "modelId": "gpt-4",
    "messages": [...],
    "temperature": 0.7,
    "maxTokens": 1000,
    "runner": "transformers",
    "hfToken": "hf_..." ,
    "connection": {
      "baseUrl": "https://api.openai.com",
      "path": "/v1/chat/completions",
      "headers": {}
    },
    "auth": {
      "type": "bearer",
      "apiKey": "..."
    }
  }
}
```

#### Embeddings

**`embedding_request`** - Single text embedding:
```json
{
  "type": "embedding_request",
  "id": "req_123",
  "payload": {
    "modelId": "sentence-transformers/all-MiniLM-L6-v2",
    "text": "Your text here",
    "hfToken": "hf_..." (optional)
  }
}
```

**`embedding_batch_request`** - Batch embeddings:
```json
{
  "type": "embedding_batch_request",
  "id": "req_123",
  "payload": {
    "modelId": "sentence-transformers/all-MiniLM-L6-v2",
    "texts": ["text1", "text2", ...],
    "hfToken": "hf_..." (optional)
  }
}
```

#### Code Indexing

**`parse_request`** - Tree-sitter code parsing:
```json
{
  "type": "parse_request",
  "id": "req_123",
  "payload": {
    "filePath": "src/main.ts",
    "content": "function hello() { ... }",
    "language": "typescript"
  }
}
```

#### vLLM Management (Optional)

**`vllm_status`** - Check vLLM runtime status:
```json
{
  "type": "vllm_status",
  "id": "req_123"
}
```

**`vllm_start`** - Start vLLM server:
```json
{
  "type": "vllm_start",
  "id": "req_123",
  "payload": {
    "model_path": "/path/to/model",
    "port": 8001
  }
}
```

**`vllm_stop`** - Stop vLLM server:
```json
{
  "type": "vllm_stop",
  "id": "req_123"
}
```

#### Health Check

**`ping`** - Connection health check:
```json
{
  "type": "ping",
  "id": "req_123"
}
```

## Backend Routing

The companion routes LLM requests to different backends based on provider and availability:

### 1. LiteLLM Proxy (Preferred for Remote Providers)

For `openai`, `anthropic`, `ollama` providers, the companion uses LiteLLM to proxy requests:
- Automatically handles provider-specific API formats
- Supports environment variables for API keys (`OPENAI_API_KEY`, `ANTHROPIC_API_KEY`)
- Falls back to direct HTTP if LiteLLM fails

### 2. Direct HTTP (OpenAI-Compatible Endpoints)

For `openai_compatible`, `lmstudio`, `vllm`, `sglang` providers, or when LiteLLM fails:
- Makes direct HTTP POST requests to the configured endpoint
- Supports custom `baseUrl`, `path`, and `headers`
- Handles bearer token and custom header authentication

### 3. Embedded vLLM Runtime (Optional, Linux + CUDA)

For `vllm` provider or `local_companion` models with "vllm" in the name:
- Routes to locally running vLLM server (default: `http://127.0.0.1:8001`)
- Requires vLLM to be installed and server running
- Automatically detects availability and reports errors if unavailable

## Features

- **Companion-First Routing**: All LLM requests automatically route through companion when connected
- **Automatic Fallback**: Seamless fallback to browser adapters if companion unavailable
- **Provider Support**: Proxy for OpenAI, Anthropic, Ollama, LM Studio, and any OpenAI-compatible endpoint
- **Centralized Auth**: Manage API keys server-side (via environment variables or request payload)
- **Code Indexing**: Tree-sitter parsing and embedding generation for semantic search
- **Optional Local Inference**: vLLM runtime support for local model inference (Linux + CUDA)

## Optional: vLLM Setup (Linux + CUDA only)

vLLM provides fast local inference for large language models but requires:
- Linux operating system
- NVIDIA GPU with CUDA support
- Python 3.12+

### Installation

1. **Install vLLM**:
   ```bash
   pip install vllm
   ```

2. **Start a vLLM server** (via companion RPC or manually):
   ```bash
   python -m vllm.entrypoints.openai.api_server --model <model_path> --port 8001
   ```

3. **Use the "Companion vLLM" model** in XEditor's model selection.

The companion will automatically detect if vLLM is available and route requests accordingly. If vLLM is unavailable (e.g., on macOS), requests will fall back to other backends or direct adapters.

## Configuration

### Port Configuration

Default port is `8000`. Change it via command line:
```bash
python main.py --port 8080
```

The web app stores the port in `localStorage` (`xeditor.companion.port`) and will reconnect automatically.

### Environment Variables

For API key management, set these environment variables (or pass in request payloads):

- `OPENAI_API_KEY` - OpenAI API key
- `ANTHROPIC_API_KEY` - Anthropic API key
- Other provider keys as needed by LiteLLM

## Troubleshooting

### Companion Not Connecting

- Check that the server is running: `curl http://localhost:8000/`
- Verify port matches web app configuration
- Check browser console for WebSocket connection errors

### Requests Falling Back to Browser

- Companion may be disconnected (check connection status in web app)
- Request may have failed (check companion server logs)
- This is expected behavior - fallback ensures reliability

### vLLM Not Available

- vLLM requires Linux + CUDA (not available on macOS/Windows)
- Install vLLM: `pip install vllm`
- Start vLLM server before using "Companion vLLM" model
- Check status via `vllm_status` RPC
