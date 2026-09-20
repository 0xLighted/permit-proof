"""Create a local-only random token without printing it or overwriting existing setup."""
import os
import secrets
from pathlib import Path

root = Path(__file__).resolve().parents[1]
path = root / ".env"
if path.exists():
    print("Existing .env kept. No credentials changed.")
else:
    content = (root / ".env.example").read_text().replace("PERMITPROOF_TOKEN=\n", f"PERMITPROOF_TOKEN={secrets.token_urlsafe(32)}\n")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(content)
    print("Created local .env with a random token. Keep it private; do not commit it.")
