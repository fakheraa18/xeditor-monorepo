# XEditor

XEditor is a prompt-native code editor that prioritizes intelligent prompt orchestration over traditional IDE features. Unlike conventional editors, XEditor recognizes that different AI models require different approaches—different prompts, different parsing strategies, and different tool configurations. It's built for developers who want to work with AI assistants that understand their codebase context and can adapt to the unique characteristics of each model family.

## What XEditor Is (And Isn't)

XEditor is a lightweight, browser-based code workspace with an AI orchestration layer at its core. It provides:

- Local folder access and file editing
- AI-powered code assistance with context awareness
- Semantic code search and indexing
- Model-aware prompt management
- Customizable tool systems per model family

XEditor is **not** a full IDE. It intentionally does not include:

- Language Server Protocol (LSP) integration
- Git integration
- Terminal emulation
- Comprehensive IDE features like refactoring tools or debuggers

The focus is on prompt intelligence and model-aware behavior, not feature completeness.

## Core Philosophy

Traditional AI coding assistants treat all models the same way—they use identical prompts, identical parsing logic, and identical tool configurations. This approach ignores a fundamental reality: models are trained differently, have different reasoning styles, and produce different output formats.

XEditor addresses this by implementing a multi-layered prompt system:

- **Mode-specific prompts**: Different interaction modes (Plan, Ask, Agent, Debug) require different approaches
- **Model family awareness**: GPT models reason differently than Claude models, which reason differently than local models
- **Version-specific optimization**: Even within the same family, different versions may benefit from tailored prompts and parsers
- **Custom parsing**: Each model family may structure responses differently, requiring specialized parsers to extract tool calls, thinking sections, and final answers

Asking all models the same way doesn't work. Parsing their responses the same way doesn't work either. XEditor provides the infrastructure to customize both.

## Architecture Overview

XEditor follows a client-server architecture with real-time communication:

### Client (Browser-Based)

The client is a Vue3 application built with Quasar2 and Monaco Editor. It runs entirely in the browser and handles:

- File editing and management
- AI chat interface
- Prompt set management UI
- Model configuration
- Indexing requests and progress display (indexing itself happens server-side)

**Data Persistence**: The client stores lightweight browser-local data in IndexedDB (chat sessions, AI configuration, UI preferences). All project data, indexes, and embeddings are stored server-side in `~/.xeditor/projects/` directory.

### Server (Local Companion)

The server is a Python FastAPI application that runs locally on your machine. It provides:

- WebSocket-based RPC communication
- LLM provider adapters (OpenAI, Anthropic, local models via transformers/vLLM)
- Tool execution engine
- Prompt set management and resolution
- **Code indexing** - All indexing operations (file scanning, parsing, embedding generation)
- **Semantic retrieval** - Vector-based code search

**Data Persistence**: Server data, including prompt sets, chat history, project configurations, and **all index data** (symbols, chunks, vectors), are stored in `~/.xeditor/` directory:

- `~/.xeditor/projects/{projectName}/` - Project data and indexes
- `~/.xeditor/llm/` - User prompt sets
- `~/.xeditor/models.json` - Model configurations

### Communication

The client and server communicate via a dual WebSocket architecture:

- **`/ws/stream`** - Dedicated to streaming operations (AI chat, LLM streaming)
- **`/ws/control`** - Handles all other RPC operations (file ops, indexing, projects, config)

This separation ensures that file change events and background operations (like incremental indexing) never interrupt active AI chat streaming. Each message has a type (e.g., `chat_message`, `execute_tool`, `list_sets`) and a payload. Streaming messages include sequence numbers for resumption support if a connection is interrupted.

### LLM Providers

XEditor supports multiple LLM providers:

- **Cloud APIs**: OpenAI (GPT family), Anthropic (Claude family), and other compatible APIs
- **Local Models**: Transformers.js for browser-based inference, or vLLM/transformers for server-side inference
- **Model Families**: GPT, Claude, Gemini, DeepSeek, Qwen, Llama, GLM, Kimi, and more

Each provider is abstracted through a common interface, allowing prompt sets to work across different backends.

### Indexing System

XEditor uses server-side indexing exclusively. The Python backend handles all indexing operations:

- File scanning and discovery (respects `.gitignore` patterns)
- TreeSitter-based AST parsing for multiple languages
- Symbol extraction and relationship mapping
- Code chunking and embedding generation
- Index storage in `~/.xeditor/projects/{projectName}/index/`

The backend companion server is **required** for indexing operations. The client sends indexing requests via WebSocket and receives real-time progress updates, but all processing happens server-side.

## Core Data Flows

Understanding how data flows through XEditor helps when debugging or contributing:

### Chat Turn Flow

For a detailed walkthrough of the end-to-end chat process, including diagrams and implementation details, see [docs/CHAT_FLOW.md](docs/CHAT_FLOW.md).

1. User sends a message in the chat interface
2. Client packages the message with context (selected code, file references) and sends via WebSocket (`chat_message` type)
3. Server's `AgentRunner` receives the message and determines the mode (agent vs simple turn)
4. Prompt resolution occurs: Mode → Set ID → Family → Version (with fallback chain)
5. Context builder gathers project information, user context, and available tools
6. System prompt is assembled with template variables replaced
7. LLM request is made with the resolved prompt
8. Response is streamed back, parsed incrementally by the mode-specific parser
9. If tool calls are detected, tools are executed (system tools via executor, custom tools via module loading)
10. Tool results are formatted and added to conversation context
11. Process repeats until no more tool calls or max steps reached
12. Final response is streamed to client as events (`content_chunk`, `tool_start`, `tool_result`, etc.)
13. Client updates UI with the streamed content

### Indexing Flow

1. User selects a folder to index in the client
2. Client sends indexing request via WebSocket (`index_build` message type) with project ID, folder paths, and embedding model configuration
3. Server's `IndexBuilder` receives the request and begins processing:
   - **Phase 1: File Scanning** - Recursively scans folders, respecting `.gitignore` patterns and default exclusions
   - **Phase 2: Parsing** - Reads files and parses with TreeSitter to extract ASTs (language-aware)
   - **Phase 3: Symbol Extraction** - Identifies functions, classes, imports/exports from ASTs
   - **Phase 4: Chunking** - Divides code into semantic chunks (functions, classes, configurable sizes)
   - **Phase 5: Embedding** - Generates embeddings for each chunk using Python transformers
   - **Phase 6: Storage** - Saves all data to `~/.xeditor/projects/{projectName}/index/` directory
4. Progress updates are streamed back to client via WebSocket (`index_progress` messages)
5. Client updates UI with progress (files processed, current phase, etc.)
6. On completion, index is ready for semantic search and retrieval

### Prompt Resolution Flow

1. User selects a mode (Plan, Ask, Agent, Debug) and a model
2. Model configuration includes: provider, model ID, family, version, and set ID
3. Resolution starts with the most specific: `{set_id}/{family}/{version}/{mode}/prompt.py`
4. If version-specific prompt doesn't exist, falls back to: `{set_id}/{family}/{mode}/prompt.py`
5. If family-specific prompt doesn't exist, falls back to default set
6. Template processor replaces variables:
   - `{{system_info}}` → OS, shell, workspace path
   - `{{tools}}` → Formatted tool descriptions from allowlist
   - `{{project_info}}` → Project name, root path, folder count
   - `{{user_context_summary}}` → Summary of user-provided context
7. Parser is resolved using the same fallback chain
8. Tools allowlist is read from `tools.json` (if exists) or falls back to legacy behavior
9. Final prompt and parser are ready for use

## Repository Structure Guide

Understanding the codebase structure helps when making contributions:

### Shipping Desktop Installers (Electron)

To produce **end-user installers** (no `npm`, no Python, no `uv` required on the user machine), use the one-command “ship” scripts on the target OS:

- **Linux (AppImage)**: `npm run ship:linux`
- **macOS (DMG)**: `npm run ship:mac`
- **Windows (NSIS + MSI)**: `npm run ship:win`

Outputs are written under `client/dist/electron/` (both installer files and packaged app folders).

### Client (`client/`)

- **`src/components/ai/`** - AI-related UI components
  - `AIPanel/` - Main chat interface with message rendering, input handling, and history
  - `SetDesigner.vue` - UI for creating and editing prompt sets
  - `ModelEditorDialog.vue` - Model configuration interface
  - `MonacoPromptEditor.vue` - Code editor for prompt files
  - `MonacoToolEditor.vue` - Code editor for custom tools

- **`src/components/editor/`** - Code editing components
  - `MonacoEditor.vue` - Monaco editor wrapper
  - `FileTree.vue` - File browser tree
  - `EditorTabs.vue` - Tab management for open files
  - `FileSearchModal.vue` - File search interface
  - `DiffView.vue` - File diff visualization

- **`src/core/indexing/`** - Indexing client and retrieval
  - `IndexOrchestrator.ts` - Sends indexing requests to backend, handles progress updates
  - `Retrieval.ts` - Semantic and text search (delegates to backend)
  - `persistence.ts` - Index data loading from backend (no local storage)

- **`src/core/llm/`** - LLM integration layer
  - `gateway.ts` - Main LLM request gateway
  - `CompanionAdapter.ts` - Adapter for local companion server
  - `ModelAdapter.ts` - Model configuration and provider abstraction

- **`src/stores/`** - Pinia state management stores
  - `chat.ts` - Chat state and history
  - `editor.ts` - Editor state (open files, selections)
  - `indexing.ts` - Indexing progress and status
  - `localCompanion.ts` - Dual WebSocket connection management (stream + control) and RPC handling
  - `project.ts` - Project configuration and folders
  - `aiConfig.ts` - AI model and prompt set configuration

### Server (`server/`)

- **`server.py`** - FastAPI application with dual WebSocket endpoints
  - `/ws/stream` - Handles streaming operations (chat, LLM) with sequence numbers
  - `/ws/control` - Handles all RPC operations and broadcasts file changes
  - Manages streaming tasks, cancellation, and stream resumption
- **`stream_buffer.py`** - Stream event buffering for resumption support
  - Buffers stream events with sequence numbers
  - Enables clients to resume interrupted streams
  - TTL-based cleanup of expired sessions

- **`agent_runner.py`** - Main agent orchestration
  - `run_agent_turn()` - Multi-step agent mode with tool calling
  - `run_simple_turn()` - Single-turn modes (Ask, Plan, Debug)
  - Coordinates prompt resolution, context building, and tool execution

- **`agent/agent.py`** - Core Agent class
  - `Agent` - Manages conversation loop with tool calling
  - `SubAgent` - Lightweight agent for tool-invoked tasks
  - Handles incremental parsing and tool call detection

- **`prompt_sets/default/`** - Built-in prompt sets
  - Organized by model family (gpt, claude, gemini, etc.)
  - Each family has mode directories (agent, ask, plan, debug)
  - Each mode contains: `prompt.py`, `parser.py`, `tools.json`
  - Optional `tools/` directory for custom tools (shared across modes)

- **`sets/manager.py`** - Prompt set management
  - Discovers bundled and user sets
  - CRUD operations for prompt sets
  - Export/import functionality (ZIP-based)
  - File operations (read/write prompt, parser, tool files)

- **`tools/`** - Tool system
  - `registry.py` - Tool discovery and allowlist checking
  - `executor.py` - System tool implementations and execution
  - `descriptions.py` - Tool descriptor generation for prompts
  - `context.py` - ToolContext class for custom tools
  - `recording.py` - Tool call recording and context policies

- **`indexing_builder.py`** - Server-side indexing (mandatory)
  - Python-based file scanning, parsing, and embedding generation
  - Handles all indexing operations, stores results in `~/.xeditor/projects/{projectName}/index/`

- **`llm.py`** - LLM provider adapters
  - Handles requests to various LLM providers
  - Manages streaming responses
  - Provider-specific configuration and authentication

- **`prompts/`** - Prompt management (legacy, being replaced by prompt sets)
  - `manager.py` - Prompt CRUD operations
  - `context_builder.py` - Context assembly for prompts
  - `template_processor.py` - Template variable replacement

### Where to Make Changes

- **Adding a new prompt set**: Create in `server/prompt_sets/default/` for bundled sets, or users create in `~/.xeditor/llm/{username}/{set-name}/`
- **Adding a custom tool**: Create Python file in `{set}/{family}/tools/` directory with `TOOL_DESCRIPTOR` and async function
- **Adding a system tool**: Implement in `server/tools/executor.py` and register in `server/tools/registry.py` SYSTEM_TOOLS list
- **UI changes**: Modify components in `client/src/components/`
- **Indexing improvements**: Work in `server/indexing_builder.py` (backend) or `client/src/core/indexing/` (client requests/UI)
- **New LLM provider**: Add adapter in `server/llm.py` and model family definition in `server/models/families.py`

## Prompt Sets System

Prompt sets are the core abstraction for model-aware behavior in XEditor. A prompt set defines how to interact with a specific model family (and optionally, a specific version) in a specific mode.

### Structure

Prompt sets follow a hierarchical structure:

```
{prompt_set}/
├── __init__.py              # SET_METADATA definition
├── {family}/                # Model family (gpt, claude, etc.)
│   ├── {mode}/              # Mode (agent, ask, plan, debug)
│   │   ├── prompt.py        # System prompt with template variables
│   │   ├── parser.py        # Response parser for this family/mode
│   │   └── tools.json       # Tool allowlist (explicit control)
│   └── tools/                # Custom tools (shared across modes)
│       ├── __init__.py
│       └── custom_tool.py    # Custom tool implementations
└── {other_family}/           # Support multiple families
```

### Components

**`__init__.py`** - Contains `SET_METADATA` dictionary:

```python
SET_METADATA = {
    "id": "default",  # or "username/set-name" for user sets
    "name": "Default Prompt Set",
    "author": "XEditor Team",
    "version": "1.0.0",
    "description": "Default prompts for all model families",
    "modes": ["agent", "ask", "plan", "debug"],
    "family": "gpt",  # Primary family
    "families": ["gpt", "claude", "gemini"],  # Supported families
    "isBuiltIn": True
}
```

**`prompt.py`** - Defines the system prompt:

```python
SYSTEM_PROMPT = """You are an AI coding assistant.

Operating System: {{system_info.os}}
Workspace: {{system_info.workspace}}

# Available Tools

{{tools}}

Follow these guidelines:
- Be helpful and concise
- Use tools when needed
"""

PARAMETERS = {
    "temperature": 0.7,
    "maxTokens": 4000,
}
```

**`parser.py`** - Extracts structured information from model responses:

```python
from parsers.base import ResponseParser, ParsedResponse

class CustomParser(ResponseParser):
    family = "gpt"

    def parse(self, content: str) -> ParsedResponse:
        # Extract thinking, tool calls, final text
        # Each model family may structure responses differently
        return ParsedResponse(
            thinking=extract_thinking(content),
            tool_call=extract_tool_call(content),
            final_text=extract_final_text(content),
        )

    def strip_tags(self, content: str) -> str:
        # Remove internal tags for display
        return content.strip()

parser = CustomParser()
```

**`tools.json`** - Explicit tool allowlist:

```json
{
  "tools": ["read_file", "write_file", "search_code", "my_custom_tool"]
}
```

Only tools listed here are:

- Included in the `{{tools}}` template variable
- Allowed to execute when the LLM calls them

If `tools.json` doesn't exist, the system falls back to legacy behavior (all system tools + all custom tools in the set).

**Custom Tools** - Defined in `{family}/tools/` directory:

```python
from typing import Dict, Any
from tools.context import ToolContext

TOOL_DESCRIPTOR = {
    "description": "Performs a custom operation.",
    "parameters": {
        "input": {
            "type": "string",
            "required": True,
            "description": "The input to process",
        },
    },
}

async def my_custom_tool(
    args: Dict[str, Any],
    context: ToolContext
) -> Dict[str, Any]:
    input_value = args.get("input", "")

    # Tool logic here
    # Can call other tools via context.execute_tool()
    # Can call LLM via context.call_llm()
    # Can search code via context.vector_search()
    # Can stream output via context.emit_tool_chunk()

    return {
        "success": True,
        "result": {"output": f"Processed: {input_value}"},
    }
```

### Template Variables

Prompts support template variables that are automatically replaced:

- **`{{system_info.os}}`** - Operating system (Linux, Windows, Darwin)
- **`{{system_info.osVersion}}`** - OS version/release
- **`{{system_info.shell}}`** - Default shell path
- **`{{system_info.home}}`** - Home directory path
- **`{{system_info.workspace}}`** - Current workspace directory
- **`{{tools}}`** - Formatted markdown documentation of all allowed tools
- **`{{project_info.name}}`** - Project name (if available)
- **`{{project_info.root}}`** - Project root path (if available)
- **`{{project_info.folderCount}}`** - Number of folders in project
- **`{{user_context_summary}}`** - Summary of user-provided context items

### Built-in vs User Sets

- **Built-in sets**: Bundled with XEditor, located in `server/prompt_sets/default/`
- **User sets**: Created by users, stored in `~/.xeditor/llm/{username}/{set-name}/`
- **Community sets**: User sets can be exported as ZIP files and shared with others

### Export/Import

Prompt sets can be exported as ZIP archives containing all files. Other users can import these ZIPs into their XEditor installation, making it easy to share custom prompt configurations with the community.

## Tools System

XEditor provides two types of tools: system tools (always available) and custom tools (defined per prompt set).

### System Tools

System tools are implemented in `server/tools/executor.py` and are always available (if allowed by `tools.json`):

- **`read_file`** - Read file contents with optional line range
- **`write_file`** - Write or create files
- **`search_code`** - Search codebase using ripgrep
- **`list_dir`** - List directory contents
- **`run_command`** - Execute shell commands
- **`create_file`** - Create new files
- **`delete_file`** - Delete files
- **`file_exists`** - Check file/directory existence
- **`search_replace`** - Find and replace text in files
- **`todo_write`** - Manage task lists
- **`semantic_search`** - Vector-based code search

System tools are executed via the `ToolExecutor` class, which handles security checks, path validation, and result formatting.

### Custom Tools

Custom tools are defined per prompt set in the `{family}/tools/` directory. They must:

1. **Include `TOOL_DESCRIPTOR`**: A dictionary that describes the tool to the LLM:

```python
TOOL_DESCRIPTOR = {
    "description": "What the tool does",
    "parameters": {
        "param_name": {
            "type": "string",  # or "number", "boolean", "object", "array"
            "required": True,
            "description": "Parameter description",
        },
    },
}
```

2. **Follow the signature**: `async def tool_name(args: Dict[str, Any], context: ToolContext) -> Dict[str, Any]`

3. **Return proper format**:

```python
return {
    "success": True,
    "result": {...},  # Any JSON-serializable data
}
# Or on error:
return {
    "success": False,
    "error": "Error message",
}
```

### ToolContext

Custom tools receive a `ToolContext` object that provides:

- **`await context.call_llm(messages, temperature, max_tokens)`** - Call the LLM (useful for sub-tasks)
- **`await context.execute_tool(tool_name, args)`** - Execute another tool
- **`await context.vector_search(query, limit)`** - Semantic code search
- **`context.get_context()`** - Get conversation context
- **`await context.emit_tool_chunk(content)`** - Stream output to UI
- **`context.project_root`** - Path to project root

### Tool Allowlisting

Tools are **not** automatically available. They must be explicitly listed in `tools.json` for the mode. This provides:

- **Security**: Only explicitly allowed tools can execute
- **Control**: Different modes can have different tool sets (e.g., Ask mode might have no tools)
- **Clarity**: Makes it obvious what tools are available

### Tool Execution Flow

1. LLM response is parsed, tool call is detected
2. Tool registry checks if tool is allowed for the current mode/set/family
3. If system tool: Executed via `ToolExecutor`
4. If custom tool: Module is loaded from `{set}/{family}/tools/{tool_name}.py`
5. Tool function is called with args and context
6. Result is formatted and added to conversation context
7. LLM receives tool result and continues

## Indexing & Retrieval System

XEditor builds a semantic index of your codebase to enable intelligent code search and context-aware AI assistance. All indexing operations are performed server-side by the local companion backend, which is **mandatory** for XEditor to function.

### Server-Side Indexing

Indexing runs entirely on the Python backend:

1. **File Scanning**: Server recursively scans project folders, respecting `.gitignore` patterns and default exclusions
2. **File Parsing**: TreeSitter parsers extract ASTs (language-aware abstract syntax trees) from source files
3. **Symbol Extraction**: Functions, classes, imports/exports are identified from ASTs
4. **Chunking**: Code is divided into semantic chunks (functions, classes, or configurable chunk sizes)
5. **Embedding Generation**: Python transformers generate embeddings for each chunk using the selected embedding model
6. **Storage**: All index data (symbols, chunks, vectors, metadata) is persisted to `~/.xeditor/projects/{projectName}/index/` directory
7. **Progress Updates**: Real-time progress is streamed to the client via WebSocket

**Index Storage**: Indexes are stored on disk at `~/.xeditor/projects/{projectName}/index/` with the following structure:

- `metadata.json` - Index manifest and file metadata
- `symbols.json` - Extracted symbols (functions, classes, etc.)
- `edges.json` - Symbol relationships (call graphs, imports)
- `chunks.json` - Code chunks with preview text
- `vectors.f32` - Binary file containing embedding vectors
- `vectors.index.json` - Index mapping chunk IDs to vector offsets

**Advantages**:

- Better performance for large codebases
- Access to more powerful embedding models
- Persistent storage that survives browser sessions
- Consistent behavior across different browsers

**Note**: The backend companion server is required for indexing. The client sends indexing requests via WebSocket and receives progress updates, but all actual processing happens server-side.

### Index Data Structure

The index consists of:

- **Symbols**: Functions, classes, imports/exports with metadata (file path, line numbers, signatures)
- **Chunks**: Semantic code units with preview text and metadata
- **Vectors**: Embedding vectors for each chunk (stored separately for efficiency)
- **File Manifests**: File metadata (path, size, last modified, content hash)
- **Manifest**: Global index metadata (file count, symbol count, embedding model ID, dimensions)

### Retrieval

XEditor supports two types of search:

- **Text Search**: Regex/token-based search using ripgrep (via `search_code` tool)
- **Semantic Search**: Vector similarity search using embeddings (via `semantic_search` tool or `vector_search` in custom tools)

Semantic search finds code that is semantically similar to the query, even if it doesn't contain the exact keywords.

## Development Workflow

### Prerequisites

- **Node.js**: Version 20 or higher
- **Python**: Version 3.12 or higher
- **Package Managers**: npm/yarn for client, uv (recommended) or pip for server
- **Git**: For version control

### Installation

**Prerequisites:**

- Install [uv](https://github.com/astral-sh/uv) (recommended for Python dependency management)
- Node.js and npm (already installed if you're here)

**Install all dependencies:**

```bash
npm run install:all
```

This command:

- Installs **Node** dependencies for both client and server workspaces via `npm install`
- Installs **Python** dependencies via `uv sync` if `uv` is available, otherwise falls back to `pip install -r requirements.txt`

**Note:** `npm run install:all` does **not** install `uv` itself. Install `uv` separately using the [official installation guide](https://github.com/astral-sh/uv#installation).

**Or install separately:**

```bash
# Frontend
cd client && npm install

# Backend
cd server && uv sync
# Alternative: pip install -r requirements.txt
```

**Optional:** Download ripgrep for better code search performance:

```bash
npm run setup:rg
```

This is optional - the app will use Python regex fallback if ripgrep is not available.

### Running in Development

XEditor requires two processes running simultaneously. **Start the server first** to avoid needing to reload the browser:

**Terminal 1 - Backend (start this first):**

```bash
npm run dev:server
# Or: cd server && uv run python main.py --reload
```

This starts the FastAPI server with auto-reload, typically on `ws://localhost:8000`

**Terminal 2 - Frontend:**

```bash
npm run dev:client
```

This starts the Quasar dev server, typically on `http://localhost:9000`

**Note:** If you start the client before the server, you may need to reload the browser once the server is up for the WebSocket connection to establish properly.

The frontend will attempt to connect to the backend via WebSocket. Ensure both are running before using AI features.

### Code Style

**Client (TypeScript/Vue)**:

- TypeScript strict mode enabled (no `any` types)
- ESLint and Prettier configured
- Vue 3 Composition API
- Pinia for state management

**Server (Python)**:

- Type hints required for function signatures
- Follow PEP 8 style guide
- Use async/await for asynchronous operations

### Testing

Currently, testing is manual. A basic smoke test:

1. Start both client and server
2. Open the application in browser
3. Verify WebSocket connection (check browser console)
4. Select a folder to index
5. Wait for indexing to complete
6. Start a chat and send a message
7. Verify AI response appears

### Building

```bash
# Build frontend for production
npm run build:client
```

The built files will be in `client/dist/` directory, ready for deployment.

### Workspace Scripts

- `npm run dev:client` - Start frontend dev server
- `npm run build:client` - Build frontend for production
- `npm run lint:client` - Lint frontend code
- `npm run format:client` - Format frontend code
- `npm run dev:server` - Start backend server with auto-reload
- `npm run install:all` - Install all dependencies

## Contribution Guidelines

XEditor welcomes contributions from the open source community. Here's how to get started:

### How to Contribute

1. **Fork the repository** and clone your fork
2. **Create a branch** for your changes (`git checkout -b feature/your-feature`)
3. **Make your changes** following the code style guidelines
4. **Test your changes** manually (see Testing section)
5. **Commit your changes** with clear, descriptive messages
6. **Push to your fork** and open a Pull Request

### Code Standards

- **TypeScript**: Use strict types, avoid `any`
- **Python**: Use type hints, follow PEP 8
- **Separation of Concerns**: Keep UI, business logic, and data access separate
- **Documentation**: Add comments for complex logic
- **Error Handling**: Handle errors gracefully with appropriate messages

### What to Contribute

Great areas for contribution:

- **New Prompt Sets**: Create prompt sets for new model families or optimize existing ones
- **Custom Tools**: Add useful custom tools to existing prompt sets
- **UI Improvements**: Enhance the user interface and user experience
- **Documentation**: Improve documentation, add examples, fix typos
- **Bug Fixes**: Fix issues reported in the issue tracker
- **Performance**: Optimize indexing, retrieval, or rendering performance

### Safe Areas for New Contributors

These areas are good starting points:

- Creating a new prompt set for a model family that isn't well-supported
- Adding custom tools to existing prompt sets
- UI polish and improvements
- Documentation improvements
- Small bug fixes

### Getting Help

If you're unsure about something:

1. Check existing issues and pull requests
2. Review the codebase structure (see Repository Structure Guide)
3. Look at similar implementations for reference
4. Open an issue with questions

## Debugging & Troubleshooting

### Common Issues

**WebSocket Connection Failures**

- Ensure the server is running (`npm run dev:server`)
- Check that the server is listening on the expected port (default: 8000)
- Verify CORS settings if connecting from a different origin
- Check browser console for connection errors

**Model Configuration Problems**

- Verify model configuration in AI Settings
- Check that API keys are set (for cloud providers)
- Ensure model family matches the provider
- Check server logs for LLM request errors

**Indexing/Embedding Provider Issues**

- Check server logs for indexing errors (file scanning, parsing, embedding generation)
- Verify embedding model is available (Python transformers downloads models on first use)
- Ensure sufficient disk space in `~/.xeditor/projects/` directory
- Check that project folder paths are accessible and readable
- Verify `.gitignore` patterns aren't excluding files you want indexed

**Tool Permission Errors**

- Verify tool is listed in `tools.json` for the current mode
- Check tool name matches exactly (case-sensitive)
- Review tool execution logs in server output
- Verify file system permissions for file operations

### Where Logs Are

- **Client**: Browser console (F12 → Console tab)
- **Server**: Terminal output where server is running
- **Debug Log**: Server writes debug information to `.cursor/debug.log` (if enabled)

### Debug Mode

Enable debug mode for chat turns to capture a full debug bundle:

- In the chat interface, enable debug mode before sending a message
- The debug bundle includes: full prompt, all messages, tool calls, responses, and timing information
- Debug bundles can be viewed in the Debug Turn Dialog

This is useful for understanding why the AI made certain decisions or why tool calls failed.

## Community & Sharing

### Sharing Prompt Sets

Prompt sets can be exported and shared with the community:

1. **Export**: Use the Set Designer UI to export a prompt set as a ZIP file
2. **Share**: Upload the ZIP to a repository, forum, or file sharing service
3. **Import**: Others can import the ZIP into their XEditor installation

This makes it easy to share optimized prompts, custom tools, and model-specific configurations.

### Community Prompt Sets

We encourage the community to create and share prompt sets. When creating a set:

- Use clear, descriptive names
- Include comprehensive `TOOL_DESCRIPTOR` for custom tools
- Create appropriate `tools.json` files for each mode
- Test with multiple models if possible
- Follow the directory structure conventions
- Use semantic versioning for updates
- Document any special requirements or use cases

### Best Practices

- **Explicit Tool Lists**: Always create `tools.json` for each mode to have precise control
- **Include TOOL_DESCRIPTOR**: Always add `TOOL_DESCRIPTOR` to custom tools
- **Use Template Variables**: Leverage `{{system_info}}`, `{{tools}}`, and other variables
- **Mode-Specific Configuration**: Different modes have different needs:
  - `ask` / `plan`: Usually no tools needed
  - `agent`: Full tool access for coding tasks
  - `debug`: Read-only tools for investigation
- **Test Thoroughly**: Test prompts with different models and scenarios

## Getting Started

### Quick Start

1. **Install dependencies**:

   ```bash
   npm run install:all
   ```

2. **Start development servers** (in two terminals, **start server first**):

   ```bash
   # Terminal 1 - Backend (start this first)
   npm run dev:server

   # Terminal 2 - Frontend
   npm run dev:client
   ```

   **Note:** Starting the server first avoids needing to reload the browser. If you start the client first, reload the browser once the server is up.

3. **Open the application**: Navigate to `http://localhost:9000` (or the port shown in terminal)

4. **Connect to companion**: The app will attempt to connect to the local companion server automatically

5. **Select a folder**: Use the folder picker to select a codebase to work with

6. **Start indexing**: The indexing process will begin automatically when you select a folder

7. **Configure AI**: Go to AI Settings to configure your preferred models and API keys

8. **Start chatting**: Open the AI panel and start a conversation

### Next Steps

- Explore the prompt sets in AI Settings
- Try different modes (Plan, Ask, Agent, Debug) to see how they differ
- Create your own prompt set or customize an existing one
- Add custom tools to extend functionality
- Index multiple projects and switch between them

## License

MIT License

Copyright (c) 2026 XEditor Team

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

## Support

For questions, issues, or contributions, please refer to the project repository or open an issue.
