#!/usr/bin/env python3
"""
PermitProof - Database Table Navigator Launcher
Run directly: python scripts/db_viewer.py [table]
Or with uv:   uv run view-db [table]
"""

import sys
from pathlib import Path

# Ensure src/ is on python import path
src_dir = str(Path(__file__).resolve().parent.parent / "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from server.scripts.db_viewer import main

if __name__ == "__main__":
    main()
