# XEditor Server (Local Companion)

The XEditor Server is a Python FastAPI application that acts as a local companion for the XEditor client. It handles heavy lifting tasks like LLM inference proxying, code indexing, and file system operations.

## Project Structure

- **`apps/`** - Application-specific backend logic
  - **`code_editor/`** - Backend for the Code Editor (Agents, Indexing, Project Management)
  - **`video_editor/`** - Backend for the Video Editor
- **`server.py`** - Main entry point and WebSocket router
- **`llm.py`** - LLM provider adapters
- **`tools/`** - Tool execution engine
- **`providers/`** - AI model providers

## Development

### Setup

Recommended using `uv` for dependency management:

```bash
# Install dependencies
uv sync
```

Or using pip:

```bash
pip install -r requirements.txt
```

### Run Development Server

```bash
# Using uv (recommended)
uv run python main.py --reload

# Or using npm script (from root)
npm run dev:server
```

The server runs on `http://localhost:8000` by default.

## Applications

### Code Editor Backend

Handles file watching, AST parsing, vector indexing, and AI agent orchestration for the Code Editor.
[Read more](./apps/code_editor/README.md)

### Video Editor Backend

Handles video processing and project management for the Video Editor.
