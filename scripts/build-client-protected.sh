#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "[xeditor] building protected client..."
cd "$ROOT_DIR"
npm run build --workspace=client

echo "[xeditor] client build complete."

