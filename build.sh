#!/usr/bin/env bash
set -e

# PermitProof Frontend Build Script (Linux / macOS)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FRONTEND_DIR="$SCRIPT_DIR/frontend"

echo "================================================================"
echo "  PERMITPROOF FRONTEND BUILD"
echo "================================================================"

if ! command -v npm &> /dev/null; then
    echo "ERROR: 'npm' was not found on your system PATH." >&2
    echo "Please install Node.js (v18+) to compile the frontend." >&2
    exit 1
fi

cd "$FRONTEND_DIR"

echo "[1/2] Synchronizing frontend dependencies via npm install..."
npm install


echo "[2/2] Compiling production bundle via npm run build..."
npm run build

echo ""
echo "================================================================"
echo "  FRONTEND COMPILED SUCCESSFULLY"
echo "  Output directory: $FRONTEND_DIR/dist"
echo "  Run server with : ./start.sh or uv run server"
echo "================================================================"
