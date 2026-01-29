#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "[xeditor] building Electron app..."
cd "$ROOT_DIR/client"

# Build Electron app (this will use the server binary from extraResources config)
quasar build -m electron

echo "[xeditor] Electron build complete."
