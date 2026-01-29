#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

PLATFORM="${XEDITOR_PLATFORM:-linux-x64}"
DIST_DIR="$ROOT_DIR/dist/xeditor-electron-$PLATFORM"

# Electron build output location (varies by platform)
# Linux: dist/electron/Unpacked or dist/electron/Packaged
# macOS: dist/electron/mac
# Windows: dist/electron/win-unpacked or dist/electron/win

ELECTRON_BUILD_DIR="$ROOT_DIR/client/dist/electron"

echo "[xeditor] packaging Electron distribution for $PLATFORM..."

if [[ ! -d "$ELECTRON_BUILD_DIR" ]]; then
  echo "[xeditor] missing Electron build at $ELECTRON_BUILD_DIR (run build-electron.sh first)" >&2
  exit 1
fi

# Find the actual Electron app directory
# electron-builder creates different structures per platform
if [[ -d "$ELECTRON_BUILD_DIR/Packaged" ]]; then
  APP_DIR="$ELECTRON_BUILD_DIR/Packaged"
elif [[ -d "$ELECTRON_BUILD_DIR/Unpacked" ]]; then
  APP_DIR="$ELECTRON_BUILD_DIR/Unpacked"
elif [[ -d "$ELECTRON_BUILD_DIR/mac" ]]; then
  APP_DIR="$ELECTRON_BUILD_DIR/mac"
elif [[ -d "$ELECTRON_BUILD_DIR/win-unpacked" ]]; then
  APP_DIR="$ELECTRON_BUILD_DIR/win-unpacked"
elif [[ -d "$ELECTRON_BUILD_DIR/win" ]]; then
  APP_DIR="$ELECTRON_BUILD_DIR/win"
else
  echo "[xeditor] could not find Electron app directory in $ELECTRON_BUILD_DIR" >&2
  echo "[xeditor] available directories:" >&2
  ls -la "$ELECTRON_BUILD_DIR" >&2 || true
  exit 1
fi

echo "[xeditor] found Electron app at: $APP_DIR"

# Create distribution directory
rm -rf "$DIST_DIR"
mkdir -p "$DIST_DIR"

# Copy the entire Electron app
cp -a "$APP_DIR/." "$DIST_DIR/"

# Create README
cat >"$DIST_DIR/README.txt" <<'EOF'
XEditor Electron Distribution

Run:
  ./xeditor (or xeditor.exe on Windows, or xeditor.app on macOS)

The Electron app will automatically:
  1. Start the local companion server
  2. Wait for it to be ready
  3. Open the UI in a native window

Environment variables (optional):
  XEDITOR_HOST=127.0.0.1
  XEDITOR_PORT=8000

Notes:
  - The server binary is bundled with the app
  - No Python or external dependencies required
  - The app runs entirely locally
EOF

echo "[xeditor] Electron distribution packaged at: $DIST_DIR"
