#!/usr/bin/env bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "================================================================"
echo "  PERMITPROOF STAGE 2 ACCESS CONTROL SERVER"
echo "================================================================"
echo "Starting backend server on port 8000 (accessible on LAN)..."
echo "Web Portal: http://localhost:8000/"
echo "Technician: http://localhost:8000/technician"
echo "Supervisor: http://localhost:8000/supervisor"
echo "Press Ctrl+C to stop the server."
echo "================================================================"

if command -v uv &> /dev/null; then
    uv run server
else
    python3 -m server.main
fi
