#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "[xeditor] building protected server (nuitka)..."
cd "$ROOT_DIR/server"

# Nuitka standalone on Linux requires patchelf.
if [[ "$(uname -s)" == "Linux" ]] && ! command -v patchelf >/dev/null 2>&1; then
  echo "[xeditor] missing dependency: patchelf" >&2
  echo "[xeditor] install it with:" >&2
  echo "  sudo apt-get update && sudo apt-get install -y patchelf" >&2
  echo "  # or: sudo dnf install -y patchelf" >&2
  echo "  # or: sudo yum install -y patchelf" >&2
  exit 1
fi

# Ensure build deps are installed (without GPU extras - they cause Nuitka linking issues)
# GPU support (onnxruntime-gpu) has complex native dependencies that Nuitka struggles with.
# The CPU version (onnxruntime) is included via light-embed and works fine.
# Users can install GPU support at runtime if needed, but it's not required for distribution.
uv sync --extra build

# Build (outputs to server/dist/)
uv run python build.py --clean --name xeditor-server

echo "[xeditor] server build complete."

