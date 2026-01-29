#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "[xeditor] building Electron app..."
cd "$ROOT_DIR"

# Build server first (required for extraResources)
echo "[xeditor] building server..."
bash "$ROOT_DIR/scripts/build-server-protected.sh"

# Build Electron app
cd "$ROOT_DIR/client"
quasar build -m electron

echo "[xeditor] Electron build complete."
