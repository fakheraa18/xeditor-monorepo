#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Check if we're running from within the packaged distribution
if [[ -d "$SCRIPT_DIR/xeditor-client" && -d "$SCRIPT_DIR/xeditor-server" ]]; then
  # Running from packaged dist directory
  DIST_ROOT="$SCRIPT_DIR"
else
  # Running from monorepo root (development)
  ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
  DIST_ROOT="${XEDITOR_DIST_ROOT:-"$ROOT_DIR/dist/xeditor-linux-x64"}"
fi

SERVER_DIR="$DIST_ROOT/xeditor-server"
CLIENT_DIR="$DIST_ROOT/xeditor-client"

SERVER_BIN="$SERVER_DIR/xeditor-server"
if [[ ! -x "$SERVER_BIN" ]]; then
  echo "[xeditor] server binary not found/executable: $SERVER_BIN" >&2
  exit 1
fi

# Client will be served by the server from the dist folder (mounted at /app).
# We only verify the directory exists.
if [[ ! -d "$CLIENT_DIR" ]]; then
  echo "[xeditor] client directory not found: $CLIENT_DIR" >&2
  exit 1
fi

HOST="${XEDITOR_HOST:-127.0.0.1}"
PORT="${XEDITOR_PORT:-8000}"

echo "[xeditor] starting server on $HOST:$PORT ..."
"$SERVER_BIN" --host "$HOST" --port "$PORT" &
SERVER_PID=$!

cleanup() {
  if kill -0 "$SERVER_PID" 2>/dev/null; then
    echo "[xeditor] stopping server..."
    kill "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
  fi
}
trap cleanup EXIT INT TERM

URL="http://$HOST:$PORT/app/"

echo "[xeditor] opening client: $URL"
if command -v xdg-open >/dev/null 2>&1; then
  xdg-open "$URL" >/dev/null 2>&1 || true
elif command -v open >/dev/null 2>&1; then
  open "$URL" >/dev/null 2>&1 || true
else
  echo "[xeditor] open this in a browser: $URL"
fi

echo "[xeditor] server running (pid $SERVER_PID). Ctrl+C to stop."
wait "$SERVER_PID"

