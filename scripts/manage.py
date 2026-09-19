#!/usr/bin/env python3
"""
PermitProof - Database Management CLI Launcher
Run directly: python scripts/manage.py [command]
Or with uv:   uv run manage [command]
"""

import sys
from pathlib import Path

# Ensure src/ is on python import path
src_dir = str(Path(__file__).resolve().parent.parent / "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from server.scripts.manage import main

if __name__ == "__main__":
    main()
