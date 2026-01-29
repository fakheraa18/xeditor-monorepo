#!/usr/bin/env bash
set -euo pipefail

# Script to download ripgrep binary for development use
# This makes rg available during development without requiring system installation

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
SERVER_DIR="$ROOT_DIR/server"

# Create bin directory in server folder for dev tools
BIN_DIR="$SERVER_DIR/bin"
mkdir -p "$BIN_DIR"

# Detect platform
if [[ "$OSTYPE" == "linux-gnu"* ]]; then
    PLATFORM="x86_64-unknown-linux-musl"
    ARCHIVE_EXT="tar.gz"
    BINARY_NAME="rg"
elif [[ "$OSTYPE" == "darwin"* ]]; then
    # Check if Apple Silicon
    if [[ $(uname -m) == "arm64" ]]; then
        PLATFORM="aarch64-apple-darwin"
    else
        PLATFORM="x86_64-apple-darwin"
    fi
    ARCHIVE_EXT="tar.gz"
    BINARY_NAME="rg"
elif [[ "$OSTYPE" == "msys" ]] || [[ "$OSTYPE" == "win32" ]]; then
    # Check if ARM64
    if [[ $(uname -m) == "arm64" ]]; then
        PLATFORM="aarch64-pc-windows-msvc"
    else
        PLATFORM="x86_64-pc-windows-msvc"
    fi
    ARCHIVE_EXT="zip"
    BINARY_NAME="rg.exe"
else
    echo "Unsupported platform: $OSTYPE" >&2
    exit 1
fi

RIPGREP_VERSION="15.1.0"
ARCHIVE_NAME="ripgrep-${RIPGREP_VERSION}-${PLATFORM}.${ARCHIVE_EXT}"
URL="https://github.com/BurntSushi/ripgrep/releases/download/${RIPGREP_VERSION}/${ARCHIVE_NAME}"
RG_BINARY="$BIN_DIR/$BINARY_NAME"
ARCHIVE_PATH="$BIN_DIR/$ARCHIVE_NAME"

# Check if already downloaded
if [[ -f "$RG_BINARY" ]]; then
    echo "[setup-dev-rg] Ripgrep already exists at $RG_BINARY"
    echo "[setup-dev-rg] To re-download, delete it first: rm $RG_BINARY"
    exit 0
fi

echo "[setup-dev-rg] Downloading ripgrep ${RIPGREP_VERSION} for ${PLATFORM}..."
echo "[setup-dev-rg] URL: $URL"

# Download archive
if command -v curl >/dev/null 2>&1; then
    curl -L -o "$ARCHIVE_PATH" "$URL"
elif command -v wget >/dev/null 2>&1; then
    wget -O "$ARCHIVE_PATH" "$URL"
else
    echo "Error: Neither curl nor wget found. Please install one of them." >&2
    exit 1
fi

# Extract archive
if [[ "$ARCHIVE_EXT" == "zip" ]]; then
    unzip -q "$ARCHIVE_PATH" -d "$BIN_DIR"
    # Find and move the binary
    find "$BIN_DIR" -name "$BINARY_NAME" -type f -exec mv {} "$RG_BINARY" \;
else
    tar -xzf "$ARCHIVE_PATH" -C "$BIN_DIR"
    # Find and move the binary
    find "$BIN_DIR" -name "$BINARY_NAME" -type f -exec mv {} "$RG_BINARY" \;
fi

# Make executable on Unix-like systems
if [[ "$OSTYPE" != "msys" ]] && [[ "$OSTYPE" != "win32" ]]; then
    chmod +x "$RG_BINARY"
fi

# Clean up archive
rm -f "$ARCHIVE_PATH"

# Clean up any extracted directories
find "$BIN_DIR" -type d -name "ripgrep-*" -exec rm -rf {} + 2>/dev/null || true

echo "[setup-dev-rg] Successfully installed ripgrep to $RG_BINARY"
echo "[setup-dev-rg] Add this to your PATH for dev mode:"
echo "[setup-dev-rg]   export PATH=\"$BIN_DIR:\$PATH\""
echo "[setup-dev-rg] Or the code will automatically find it in $BIN_DIR"
