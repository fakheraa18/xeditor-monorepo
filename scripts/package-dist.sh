#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

PLATFORM="${XEDITOR_PLATFORM:-linux-x64}"
DIST_DIR="$ROOT_DIR/dist/xeditor-$PLATFORM"

CLIENT_BUILD_DIR="$ROOT_DIR/client/dist/spa"
SERVER_BUILD_DIR="$ROOT_DIR/server/dist/xeditor-server.dist"

echo "[xeditor] packaging distribution for $PLATFORM..."
rm -rf "$DIST_DIR"
mkdir -p "$DIST_DIR"

if [[ ! -d "$CLIENT_BUILD_DIR" ]]; then
  echo "[xeditor] missing client build at $CLIENT_BUILD_DIR (run build first)" >&2
  exit 1
fi

if [[ ! -d "$SERVER_BUILD_DIR" ]]; then
  echo "[xeditor] missing server build at $SERVER_BUILD_DIR (run build first)" >&2
  exit 1
fi

mkdir -p "$DIST_DIR/xeditor-client"
mkdir -p "$DIST_DIR/xeditor-server"

cp -a "$CLIENT_BUILD_DIR/." "$DIST_DIR/xeditor-client/"
cp -a "$SERVER_BUILD_DIR/." "$DIST_DIR/xeditor-server/"

cp "$ROOT_DIR/scripts/launcher.sh" "$DIST_DIR/launcher.sh"
chmod +x "$DIST_DIR/launcher.sh" || true

cat >"$DIST_DIR/README.txt" <<'EOF'
XEditor (protected distribution)

Run:
  ./launcher.sh

Environment variables:
  XEDITOR_HOST=127.0.0.1
  XEDITOR_PORT=8000

Notes:
  - The server runs locally (no Python required).
  - The client is served by the server at /app (do not use file://).
EOF

echo "[xeditor] packaged at: $DIST_DIR"

