#!/usr/bin/env python3
"""
PermitProof - Database Seeder Launcher
Run directly: python scripts/seed.py
Or with uv:   uv run seed
"""

import sys
from pathlib import Path

# Ensure src/ is on python import path
src_dir = str(Path(__file__).resolve().parent.parent / "src")
if src_dir not in sys.path:
    sys.path.insert(0, src_dir)

from server.scripts.seed import seed_database

if __name__ == "__main__":
    seed_database()
