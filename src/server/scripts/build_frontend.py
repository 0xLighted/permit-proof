"""
PermitProof - Frontend Compilation Script
Compiles the React / Vite frontend bundle into frontend/dist.
"""

import os
import shutil
import subprocess
import sys


def main():
    repo_root = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "..")
    )
    frontend_dir = os.path.join(repo_root, "frontend")
    dist_dir = os.path.join(frontend_dir, "dist")
    node_modules = os.path.join(frontend_dir, "node_modules")

    print("=" * 70)
    print("  PERMITPROOF FRONTEND COMPILER")
    print("=" * 70)
    print(f"Frontend Directory: {frontend_dir}")
    print(f"Output Directory  : {dist_dir}")

    npm_cmd = shutil.which("npm")
    if not npm_cmd:
        print("\n[ERROR] 'npm' was not found on your system PATH.", file=sys.stderr)
        print("Please install Node.js (v18+) to compile the frontend.", file=sys.stderr)
        sys.exit(1)

    print("\n[1/2] Synchronizing frontend dependencies via npm install...")
    res = subprocess.run([npm_cmd, "install"], cwd=frontend_dir)
    if res.returncode != 0:
        print("[ERROR] npm install failed.", file=sys.stderr)
        sys.exit(res.returncode)

    print("\n[2/2] Compiling production bundle via npm run build...")
    res = subprocess.run([npm_cmd, "run", "build"], cwd=frontend_dir)
    if res.returncode != 0:
        print("[ERROR] npm run build failed.", file=sys.stderr)
        sys.exit(res.returncode)

    print("\n" + "=" * 70)
    print("  FRONTEND BUILD SUCCESSFUL")
    print(f"  Compiled bundle ready at: {dist_dir}")
    print("  FastAPI will now serve the SPA at http://localhost:8000/")
    print("=" * 70 + "\n")


if __name__ == "__main__":
    main()
