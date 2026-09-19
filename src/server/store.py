"""
PermitProof - Stage 2 In-Memory Mock Store
Tracks devices, users, jobs pre-approvals, challenges, attempts, and approval links
without requiring SQLite database integration.
"""

import time
import asyncio
from typing import Dict, Any, Optional, List, Tuple


class MemoryStore:
    def __init__(self):
        self.devices: Dict[str, Dict[str, Any]] = {}
        self.users: Dict[str, Dict[str, Any]] = {}
        self.jobs: Dict[str, Dict[str, Any]] = {}
        self.challenges: Dict[str, Dict[str, Any]] = {}
        self.access_attempts: Dict[str, Dict[str, Any]] = {}
        self.approval_links: Dict[str, Dict[str, Any]] = {}  # token_hash -> dict
        self.raw_approval_tokens: Dict[str, str] = {}         # token -> attempt_id (for fast lookup)
        self.attempt_events: Dict[str, asyncio.Event] = {}    # attempt_id -> event for held GET
        self.audit_events: List[Dict[str, Any]] = []

    def reset(self):
        """Clears all store state."""
        self.devices.clear()
        self.users.clear()
        self.jobs.clear()
        self.challenges.clear()
        self.access_attempts.clear()
        self.approval_links.clear()
        self.raw_approval_tokens.clear()
        self.attempt_events.clear()
        self.audit_events.clear()

    # --- Devices ---
    def register_device(self, device_id_hash: str, room_id: str = "room-101", active: bool = True, display_name: str = "Pi Server Room Reader"):
        self.devices[device_id_hash] = {
            "device_id_hash": device_id_hash,
            "room_id": room_id,
            "active": active,
            "display_name": display_name
        }

    def get_device(self, device_id_hash: str) -> Optional[Dict[str, Any]]:
        device = self.devices.get(device_id_hash)
        if device and device.get("active"):
            return device
        return None

    # --- Users ---
    def register_user(self, card_id_hash: str, full_name: str, email: str, role: str = "technician", active: bool = True):
        self.users[card_id_hash] = {
            "card_id_hash": card_id_hash,
            "full_name": full_name,
            "email": email,
            "role": role,
            "active": active
        }

    def get_user(self, card_id_hash: str) -> Optional[Dict[str, Any]]:
        user = self.users.get(card_id_hash)
        if user and user.get("active"):
            return user
        return None

    # --- Jobs Pre-Approval ---
    def add_job(self, job_id: str, supervisor_id: str, technician_id: str, device_id_hash: str, status: str = "accepted", is_complete: int = 0):
        self.jobs[job_id] = {
            "job_id": job_id,
            "supervisor_id": supervisor_id,
            "technician_id": technician_id,
            "device_id_hash": device_id_hash,
            "status": status,
            "is_complete": is_complete,
            "created_at": time.time(),
            "accepted_at": time.time()
        }

    def find_accepted_job(self, card_id_hash: str, device_id_hash: str) -> Optional[Dict[str, Any]]:
        """
        Finds an accepted, incomplete job matching technician card hash and device hash.
        """
        for job in self.jobs.values():
            if (job["technician_id"] == card_id_hash and
                job["device_id_hash"] == device_id_hash and
                job["status"] == "accepted" and
                job["is_complete"] == 0):
                return job
        return None

    # --- Challenges / Nonces ---
    def save_challenge(self, nonce: str, device_id_hash: str, lifetime_seconds: int = 30):
        now = time.time()
        self.challenges[nonce] = {
            "nonce": nonce,
            "device_id_hash": device_id_hash,
            "issued_at": now,
            "expires_at": now + lifetime_seconds,
            "consumed_at": None
        }

    def consume_nonce(self, nonce: str, device_id_hash: str) -> Tuple[bool, str]:
        """
        Atomically consumes the nonce only if:
        - It belongs to device_id_hash
        - It is unused (consumed_at is None)
        - Current time is within expires_at (30s)
        """
        now = time.time()
        challenge = self.challenges.get(nonce)
        if not challenge:
            return False, "UNKNOWN_NONCE"
        if challenge["device_id_hash"] != device_id_hash:
            return False, "NONCE_DEVICE_MISMATCH"
        if challenge["consumed_at"] is not None:
            return False, "NONCE_ALREADY_CONSUMED"
        if now > challenge["expires_at"]:
            return False, "NONCE_EXPIRED"

        challenge["consumed_at"] = now
        return True, "CONSUMED"

    # --- Access Attempts & Async Held Results ---
    def create_attempt(self, attempt_id: str, device_id_hash: str, card_id_hash: str, job_id: str, result_token_hash: str, lifetime_seconds: int = 120):
        now = time.time()
        self.access_attempts[attempt_id] = {
            "attempt_id": attempt_id,
            "device_id_hash": device_id_hash,
            "card_id_hash": card_id_hash,
            "job_id": job_id,
            "status": "PENDING_EMAIL_APPROVAL",
            "created_at": now,
            "expires_at": now + lifetime_seconds,
            "decided_at": None,
            "result_token_hash": result_token_hash,
            "decision": None
        }
        self.attempt_events[attempt_id] = asyncio.Event()

    def get_attempt(self, attempt_id: str) -> Optional[Dict[str, Any]]:
        return self.access_attempts.get(attempt_id)

    def get_attempt_event(self, attempt_id: str) -> asyncio.Event:
        if attempt_id not in self.attempt_events:
            self.attempt_events[attempt_id] = asyncio.Event()
        return self.attempt_events[attempt_id]

    def approve_attempt(self, attempt_id: str) -> bool:
        now = time.time()
        attempt = self.access_attempts.get(attempt_id)
        if not attempt:
            return False
        if attempt["status"] != "PENDING_EMAIL_APPROVAL":
            return False
        if now > attempt["expires_at"]:
            attempt["status"] = "EXPIRED"
            attempt["decision"] = "ACCESS_DENIED"
            attempt["decided_at"] = now
            self.get_attempt_event(attempt_id).set()
            return False

        attempt["status"] = "APPROVED"
        attempt["decision"] = "ACCESS_GRANTED"
        attempt["decided_at"] = now
        self.get_attempt_event(attempt_id).set()
        return True

    def reject_attempt(self, attempt_id: str, reason: str = "REJECTED") -> bool:
        now = time.time()
        attempt = self.access_attempts.get(attempt_id)
        if not attempt:
            return False
        attempt["status"] = "REJECTED"
        attempt["decision"] = "ACCESS_DENIED"
        attempt["decided_at"] = now
        attempt["reason"] = reason
        self.get_attempt_event(attempt_id).set()
        return True

    # --- Approval Links (Magic Email Tokens) ---
    def save_approval_token(self, raw_token: str, token_hash: str, attempt_id: str, expires_in_seconds: int = 120):
        now = time.time()
        self.approval_links[token_hash] = {
            "token_hash": token_hash,
            "attempt_id": attempt_id,
            "created_at": now,
            "expires_at": now + expires_in_seconds,
            "used_at": None
        }
        self.raw_approval_tokens[raw_token] = token_hash

    def consume_approval_token(self, raw_token: str) -> Tuple[bool, Optional[str], str]:
        """
        Consumes an email magic link token atomically.
        Returns (success, attempt_id, reason).
        """
        token_hash = self.raw_approval_tokens.get(raw_token)
        if not token_hash:
            return False, None, "INVALID_TOKEN"

        link = self.approval_links.get(token_hash)
        if not link:
            return False, None, "INVALID_TOKEN"

        now = time.time()
        if link["used_at"] is not None:
            return False, link["attempt_id"], "ALREADY_USED"

        if now > link["expires_at"]:
            return False, link["attempt_id"], "EXPIRED"

        link["used_at"] = now
        attempt_id = link["attempt_id"]
        approved = self.approve_attempt(attempt_id)
        if approved:
            return True, attempt_id, "APPROVED"
        return False, attempt_id, "ATTEMPT_NOT_PENDING"

    # --- Audit Log ---
    def log_audit_event(self, event_type: str, outcome: str, attempt_id: Optional[str] = None, device_hash: Optional[str] = None, card_hash: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None):
        self.audit_events.append({
            "timestamp": time.time(),
            "event_type": event_type,
            "outcome": outcome,
            "attempt_id": attempt_id,
            "device_hash": device_hash,
            "card_hash": card_hash,
            "metadata": metadata or {}
        })


store = MemoryStore()
