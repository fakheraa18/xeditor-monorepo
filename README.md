# XEditor Monorepo

XEditor is a platform for building AI-native developer tools. It currently hosts two main applications:

1.  **Code Editor**: A prompt-native code editor that prioritizes intelligent prompt orchestration over traditional IDE features.
2.  **Video Editor**: A video editing application integrated into the same workspace.

## Repository Structure

This is a monorepo containing both the frontend client and the backend server.

- **`client/`**: Vue 3 + Quasar 2 frontend application.
  - Contains the UI for both Code Editor and Video Editor.
  - [Client Documentation](./client/README.md)
- **`server/`**: Python FastAPI backend (Local Companion).
  - Handles local operations, LLM proxying, indexing, and app-specific backend logic.
  - [Server Documentation](./server/README.md)

## Getting Started

### Prerequisites

- **Node.js**: Version 20 or higher
- **Python**: Version 3.12 or higher
- **Package Managers**: npm/yarn for client, uv (recommended) or pip for server

### Installation

**Install all dependencies:**

```bash
npm run install:all
```

This command installs dependencies for both the client and the server.

### Running in Development

XEditor requires both the client and server processes running simultaneously.

**Terminal 1 - Backend (start this first):**

```bash
npm run dev:server
```

**Terminal 2 - Frontend:**

```bash
npm run dev:client
```

Open your browser to `http://localhost:9000`. You will see a launcher page to select between the Code Editor and Video Editor.

## Core Philosophy (Code Editor)

The Code Editor application is built on the belief that different AI models require different approaches. It implements a multi-layered prompt system:

- **Mode-specific prompts**: Different interaction modes (Plan, Ask, Agent, Debug)
- **Model family awareness**: Tailored prompts for GPT, Claude, etc.
- **Custom parsing**: Specialized parsers for different model outputs

[Read more about the Code Editor Philosophy](./client/src/apps/CodeEditor/README.md)

## Architecture

XEditor follows a client-server architecture with real-time communication via WebSockets.

- **Client**: Browser-based UI, handles file editing, chat interface, and app switching.
- **Server**: Local Python server, handles file I/O, indexing, LLM requests, and heavy computation.

The server exposes a dual WebSocket architecture:

- `/ws/stream`: For streaming operations (AI chat, LLM responses).
- `/ws/control`: For RPC operations (file system, project management).

## License

MIT License

Copyright (c) 2026 XEditor Team
