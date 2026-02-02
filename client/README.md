# XEditor Client

The XEditor client is a Vue 3 + Quasar 2 application that serves as the frontend for the XEditor platform. It supports multiple applications running within a unified interface.

## Project Structure

- **`src/apps/`** - Application-specific code
  - **`CodeEditor/`** - The AI-native code editor (formerly the main app)
  - **`VideoEditor/`** - The video editing application
- **`src/components/`** - Shared UI components
- **`src/core/`** - Core logic (LLM gateway, Indexing client, etc.)
- **`src/stores/`** - Pinia state management stores
- **`src/layouts/`** - Shared layouts
- **`src/pages/`** - Shared pages (Launcher, Settings)

## Development

### Setup

```bash
npm install
```

### Run Development Server

```bash
npm run dev
```

This starts the Quasar development server, typically at `http://localhost:9000`.

### Build

```bash
npm run build
```

The build output will be in `dist/spa`.

## Applications

### Code Editor

A prompt-native code editor focused on AI orchestration.
[Read more](./src/apps/CodeEditor/README.md)

### Video Editor

A video editing application integrated into the XEditor platform.
