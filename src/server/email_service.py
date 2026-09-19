"""
PermitProof - Stage 2 Email Dispatcher
Handles delivering one-time magic links out-of-band to card owners.
Maintains a clean in-memory outbox for testing and demonstration without leaking
secret tokens into persistent SQLite audit logs.
"""

import time
from typing import Dict, Any, List, Optional


class EmailDispatcher:
    def __init__(self):
        self._outbox: List[Dict[str, Any]] = []

    def send_magic_link(
        self,
        to_name: str,
        to_email: str,
        attempt_id: str,
        approval_url: str,
        email_token: str
    ):
        entry = {
            "timestamp": time.time(),
            "to_name": to_name,
            "to_email": to_email,
            "attempt_id": attempt_id,
            "approval_url": approval_url,
            "email_token": email_token
        }
        self._outbox.append(entry)
        if len(self._outbox) > 200:
            self._outbox.pop(0)

        print("\n" + "=" * 70)
        print(f"[STAGE 2 EMAIL DISPATCH SIMULATED]")
        print(f"  To: {to_name} <{to_email}>")
        print(f"  Attempt ID: {attempt_id}")
        print(f"  One-Time Magic Approval Link: {approval_url}")
        print("=" * 70 + "\n")

    def get_latest_token(self, attempt_id: Optional[str] = None) -> Optional[str]:
        for entry in reversed(self._outbox):
            if attempt_id is None or entry["attempt_id"] == attempt_id:
                return entry["email_token"]
        return None

    def get_latest_entry(self, attempt_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        for entry in reversed(self._outbox):
            if attempt_id is None or entry["attempt_id"] == attempt_id:
                return dict(entry)
        return None

    def clear_outbox(self):
        self._outbox.clear()


email_service = EmailDispatcher()
