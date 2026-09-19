"""
PermitProof - Stage 2 SQLite Database Engine
Implements the full database schema, connection pooling, and atomic transactions
per STAGE2_HANDOFF.md.
"""

import sqlite3
import os
import json
import time
from typing import Optional, Dict, Any, List, Tuple
from contextlib import contextmanager

DEFAULT_DB_PATH = "permitproof.db"


def get_db_path() -> str:
    return os.environ.get("DATABASE_PATH", DEFAULT_DB_PATH)


def connect_db(db_path: Optional[str] = None) -> sqlite3.Connection:
    """
    Connects to SQLite with WAL mode, foreign keys enabled, and Row factory.
    """
    path = db_path or get_db_path()
    conn = sqlite3.connect(path, timeout=10.0)
    conn.row_factory = sqlite3.Row
    # Enforce foreign keys on every connection
    conn.execute("PRAGMA foreign_keys = ON;")
    # WAL mode helps concurrent reads while API writes (for file databases)
    if path != ":memory:":
        conn.execute("PRAGMA journal_mode = WAL;")
    return conn


@contextmanager
def get_db_cursor(db_path: Optional[str] = None):
    conn = connect_db(db_path)
    try:
        cursor = conn.cursor()
        yield cursor
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: Optional[str] = None):
    """
    Initializes all 7 required tables with foreign keys and strict constraints.
    """
    schema = """
    CREATE TABLE IF NOT EXISTS users (
        card_id_hash TEXT PRIMARY KEY,
        full_name TEXT NOT NULL,
        email TEXT NOT NULL,
        role TEXT NOT NULL CHECK(role IN ('supervisor', 'technician')),
        active INTEGER NOT NULL DEFAULT 1
    );

    CREATE TABLE IF NOT EXISTS devices (
        device_id_hash TEXT PRIMARY KEY,
        room_id TEXT NOT NULL UNIQUE,
        active INTEGER NOT NULL DEFAULT 1,
        display_name TEXT
    );

    CREATE TABLE IF NOT EXISTS jobs (
        job_id TEXT PRIMARY KEY,
        created_at REAL NOT NULL,
        supervisor_id TEXT NOT NULL REFERENCES users(card_id_hash),
        technician_id TEXT NOT NULL REFERENCES users(card_id_hash),
        device_id_hash TEXT NOT NULL REFERENCES devices(device_id_hash),
        tasks_json TEXT NOT NULL DEFAULT '[]',
        status TEXT NOT NULL CHECK(status IN ('pending', 'accepted', 'skipped', 'completed', 'revoked')),
        is_complete INTEGER NOT NULL DEFAULT 0 CHECK((status = 'completed' AND is_complete = 1) OR (status != 'completed' AND is_complete = 0)),
        accepted_at REAL,
        completed_at REAL,
        revoked_at REAL
    );

    CREATE TABLE IF NOT EXISTS challenges (
        nonce TEXT PRIMARY KEY,
        device_id_hash TEXT NOT NULL REFERENCES devices(device_id_hash),
        issued_at REAL NOT NULL,
        expires_at REAL NOT NULL,
        consumed_at REAL
    );

    CREATE TABLE IF NOT EXISTS access_attempts (
        attempt_id TEXT PRIMARY KEY,
        device_id_hash TEXT NOT NULL REFERENCES devices(device_id_hash),
        card_id_hash TEXT NOT NULL REFERENCES users(card_id_hash),
        job_id TEXT NOT NULL REFERENCES jobs(job_id),
        status TEXT NOT NULL CHECK(status IN ('PENDING_EMAIL_APPROVAL', 'APPROVED', 'REJECTED', 'EXPIRED')),
        created_at REAL NOT NULL,
        expires_at REAL NOT NULL,
        decided_at REAL,
        result_token_hash TEXT NOT NULL,
        decision TEXT,
        reason TEXT
    );

    CREATE TABLE IF NOT EXISTS approval_links (
        token_hash TEXT PRIMARY KEY,
        attempt_id TEXT NOT NULL REFERENCES access_attempts(attempt_id),
        created_at REAL NOT NULL,
        expires_at REAL NOT NULL,
        used_at REAL
    );

    CREATE TABLE IF NOT EXISTS audit_events (
        event_id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp REAL NOT NULL,
        attempt_id TEXT,
        device_hash TEXT,
        card_hash TEXT,
        event_type TEXT NOT NULL,
        outcome TEXT NOT NULL,
        metadata_json TEXT
    );

    -- Indices for high performance lookups
    CREATE INDEX IF NOT EXISTS idx_jobs_tech_device_status ON jobs(technician_id, device_id_hash, status, is_complete);
    CREATE INDEX IF NOT EXISTS idx_challenges_expires ON challenges(expires_at, consumed_at);
    CREATE INDEX IF NOT EXISTS idx_approval_links_attempt ON approval_links(attempt_id);
    """
    with get_db_cursor(db_path) as cursor:
        cursor.executescript(schema)


# ==============================================================================
# Database Access Layer
# ==============================================================================

class DatabaseManager:
    def __init__(self, db_path: Optional[str] = None):
        self._db_path = db_path

    @property
    def db_path(self) -> str:
        return self._db_path or get_db_path()

    def init_schema(self):
        init_db(self.db_path)

    # --- Users ---
    def upsert_user(self, card_id_hash: str, full_name: str, email: str, role: str, active: int = 1):
        with get_db_cursor(self.db_path) as c:
            c.execute("""
            INSERT INTO users (card_id_hash, full_name, email, role, active)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(card_id_hash) DO UPDATE SET
                full_name=excluded.full_name,
                email=excluded.email,
                role=excluded.role,
                active=excluded.active
            """, (card_id_hash, full_name, email, role, active))

    def get_user(self, card_id_hash: str) -> Optional[Dict[str, Any]]:
        with get_db_cursor(self.db_path) as c:
            c.execute("SELECT * FROM users WHERE card_id_hash = ? AND active = 1", (card_id_hash,))
            row = c.fetchone()
            return dict(row) if row else None

    def list_users(self, active_only: bool = False) -> List[Dict[str, Any]]:
        with get_db_cursor(self.db_path) as c:
            if active_only:
                c.execute("SELECT * FROM users WHERE active = 1 ORDER BY full_name")
            else:
                c.execute("SELECT * FROM users ORDER BY full_name")
            return [dict(r) for r in c.fetchall()]

    def delete_user(self, card_id_hash: str) -> bool:
        with get_db_cursor(self.db_path) as c:
            c.execute("DELETE FROM users WHERE card_id_hash = ?", (card_id_hash,))
            return c.rowcount > 0

    # --- Devices ---
    def upsert_device(self, device_id_hash: str, room_id: str, active: int = 1, display_name: Optional[str] = None):
        with get_db_cursor(self.db_path) as c:
            c.execute("""
            INSERT INTO devices (device_id_hash, room_id, active, display_name)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(device_id_hash) DO UPDATE SET
                room_id=excluded.room_id,
                active=excluded.active,
                display_name=excluded.display_name
            """, (device_id_hash, room_id, active, display_name))

    def get_device(self, device_id_hash: str) -> Optional[Dict[str, Any]]:
        with get_db_cursor(self.db_path) as c:
            c.execute("SELECT * FROM devices WHERE device_id_hash = ? AND active = 1", (device_id_hash,))
            row = c.fetchone()
            return dict(row) if row else None

    def list_devices(self, active_only: bool = False) -> List[Dict[str, Any]]:
        with get_db_cursor(self.db_path) as c:
            if active_only:
                c.execute("SELECT * FROM devices WHERE active = 1 ORDER BY room_id")
            else:
                c.execute("SELECT * FROM devices ORDER BY room_id")
            return [dict(r) for r in c.fetchall()]

    def delete_device(self, device_id_hash: str) -> bool:
        with get_db_cursor(self.db_path) as c:
            c.execute("DELETE FROM devices WHERE device_id_hash = ?", (device_id_hash,))
            return c.rowcount > 0

    # --- Jobs Pre-Approval ---
    def create_job(self, job_id: str, supervisor_id: str, technician_id: str, device_id_hash: str, tasks: List[str]) -> Dict[str, Any]:
        # Validate tasks are strings
        if not isinstance(tasks, list) or not all(isinstance(t, str) for t in tasks):
            raise ValueError("Tasks must be a list of strings")
        now = time.time()
        tasks_json = json.dumps(tasks)
        with get_db_cursor(self.db_path) as c:
            c.execute("""
            INSERT INTO jobs (job_id, created_at, supervisor_id, technician_id, device_id_hash, tasks_json, status, is_complete)
            VALUES (?, ?, ?, ?, ?, ?, 'pending', 0)
            """, (job_id, now, supervisor_id, technician_id, device_id_hash, tasks_json))
        return {
            "job_id": job_id,
            "created_at": now,
            "supervisor_id": supervisor_id,
            "technician_id": technician_id,
            "device_id_hash": device_id_hash,
            "tasks": tasks,
            "status": "pending",
            "is_complete": 0
        }

    def update_job_status(self, job_id: str, new_status: str, technician_id: Optional[str] = None) -> Tuple[bool, str]:
        now = time.time()
        with get_db_cursor(self.db_path) as c:
            c.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,))
            job = c.fetchone()
            if not job:
                return False, "JOB_NOT_FOUND"

            # Enforce authorization if technician_id specified
            if technician_id and job["technician_id"] != technician_id:
                return False, "UNAUTHORIZED_TECHNICIAN"

            current_status = job["status"]
            if current_status in ("completed", "revoked"):
                return False, f"CANNOT_CHANGE_TERMINAL_JOB_{current_status.upper()}"

            if new_status == "accepted":
                c.execute("UPDATE jobs SET status = 'accepted', accepted_at = ? WHERE job_id = ?", (now, job_id))
            elif new_status == "skipped":
                c.execute("UPDATE jobs SET status = 'skipped' WHERE job_id = ?", (job_id,))
            elif new_status == "completed":
                c.execute("UPDATE jobs SET status = 'completed', is_complete = 1, completed_at = ? WHERE job_id = ?", (now, job_id))
            elif new_status == "revoked":
                c.execute("UPDATE jobs SET status = 'revoked', revoked_at = ? WHERE job_id = ?", (now, job_id))
            else:
                return False, f"INVALID_STATUS_{new_status}"

        return True, "SUCCESS"

    def find_accepted_job(self, technician_id: str, device_id_hash: str) -> Optional[Dict[str, Any]]:
        with get_db_cursor(self.db_path) as c:
            c.execute("""
            SELECT * FROM jobs
            WHERE technician_id = ? AND device_id_hash = ? AND status = 'accepted' AND is_complete = 0
            ORDER BY accepted_at ASC LIMIT 1
            """, (technician_id, device_id_hash))
            row = c.fetchone()
            if row:
                d = dict(row)
                d["tasks"] = json.loads(d["tasks_json"])
                return d
            return None

    def list_jobs(self, technician_id: Optional[str] = None, status: Optional[str] = None) -> List[Dict[str, Any]]:
        query = "SELECT * FROM jobs WHERE 1=1"
        params = []
        if technician_id:
            query += " AND technician_id = ?"
            params.append(technician_id)
        if status:
            query += " AND status = ?"
            params.append(status)
        query += " ORDER BY created_at DESC"

        with get_db_cursor(self.db_path) as c:
            c.execute(query, tuple(params))
            results = []
            for row in c.fetchall():
                d = dict(row)
                d["tasks"] = json.loads(d["tasks_json"])
                results.append(d)
            return results

    def delete_job(self, job_id: str) -> bool:
        with get_db_cursor(self.db_path) as c:
            c.execute("DELETE FROM jobs WHERE job_id = ?", (job_id,))
            return c.rowcount > 0

    # --- Challenges / Nonces ---
    def save_challenge(self, nonce: str, device_id_hash: str, lifetime_seconds: int = 30):
        now = time.time()
        with get_db_cursor(self.db_path) as c:
            c.execute("""
            INSERT INTO challenges (nonce, device_id_hash, issued_at, expires_at, consumed_at)
            VALUES (?, ?, ?, ?, NULL)
            """, (nonce, device_id_hash, now, now + lifetime_seconds))

    def consume_nonce_atomic(self, nonce: str, device_id_hash: str) -> Tuple[bool, str]:
        now = time.time()
        with get_db_cursor(self.db_path) as c:
            # 1. Attempt atomic update
            c.execute("""
            UPDATE challenges
            SET consumed_at = ?
            WHERE nonce = ? AND device_id_hash = ? AND consumed_at IS NULL AND expires_at >= ?
            """, (now, nonce, device_id_hash, now))

            if c.rowcount == 1:
                return True, "CONSUMED"

            # 2. Diagnosing reason if update did not affect 1 row
            c.execute("SELECT * FROM challenges WHERE nonce = ?", (nonce,))
            row = c.fetchone()
            if not row:
                return False, "UNKNOWN_NONCE"
            if row["device_id_hash"] != device_id_hash:
                return False, "NONCE_DEVICE_MISMATCH"
            if row["consumed_at"] is not None:
                return False, "NONCE_ALREADY_CONSUMED"
            if now > row["expires_at"]:
                return False, "NONCE_EXPIRED"

            return False, "NONCE_CONSUMPTION_FAILED"

    def prune_expired_challenges(self, max_age_seconds: float = 86400) -> int:
        """Removes challenges older than max_age_seconds to prevent table bloat."""
        cutoff = time.time() - max_age_seconds
        with get_db_cursor(self.db_path) as c:
            c.execute("DELETE FROM challenges WHERE expires_at < ?", (cutoff,))
            return c.rowcount

    # --- Access Attempts ---
    def create_attempt(self, attempt_id: str, device_id_hash: str, card_id_hash: str, job_id: str, result_token_hash: str, lifetime_seconds: int = 120):
        now = time.time()
        with get_db_cursor(self.db_path) as c:
            c.execute("""
            INSERT INTO access_attempts (
                attempt_id, device_id_hash, card_id_hash, job_id, status, created_at, expires_at, decided_at, result_token_hash, decision
            ) VALUES (?, ?, ?, ?, 'PENDING_EMAIL_APPROVAL', ?, ?, NULL, ?, NULL)
            """, (attempt_id, device_id_hash, card_id_hash, job_id, now, now + lifetime_seconds, result_token_hash))

    def get_attempt(self, attempt_id: str) -> Optional[Dict[str, Any]]:
        with get_db_cursor(self.db_path) as c:
            c.execute("SELECT * FROM access_attempts WHERE attempt_id = ?", (attempt_id,))
            row = c.fetchone()
            return dict(row) if row else None

    def update_attempt_decision(self, attempt_id: str, new_status: str, decision: str, reason: Optional[str] = None) -> bool:
        now = time.time()
        with get_db_cursor(self.db_path) as c:
            c.execute("""
            UPDATE access_attempts
            SET status = ?, decision = ?, decided_at = ?, reason = ?
            WHERE attempt_id = ? AND status = 'PENDING_EMAIL_APPROVAL'
            """, (new_status, decision, now, reason, attempt_id))
            return c.rowcount == 1

    # --- Approval Links (Magic Email Tokens) ---
    def save_approval_link(self, token_hash: str, attempt_id: str, lifetime_seconds: int = 120):
        now = time.time()
        with get_db_cursor(self.db_path) as c:
            c.execute("""
            INSERT INTO approval_links (token_hash, attempt_id, created_at, expires_at, used_at)
            VALUES (?, ?, ?, ?, NULL)
            """, (token_hash, attempt_id, now, now + lifetime_seconds))

    def consume_approval_token_atomic(self, token_hash: str) -> Tuple[bool, Optional[str], str]:
        now = time.time()
        with get_db_cursor(self.db_path) as c:
            # 1. Atomically consume token
            c.execute("""
            UPDATE approval_links
            SET used_at = ?
            WHERE token_hash = ? AND used_at IS NULL AND expires_at >= ?
            """, (now, token_hash, now))

            if c.rowcount == 1:
                # Token consumed; retrieve attempt_id
                c.execute("SELECT attempt_id FROM approval_links WHERE token_hash = ?", (token_hash,))
                attempt_id = c.fetchone()["attempt_id"]

                # Atomically approve attempt
                c.execute("""
                UPDATE access_attempts
                SET status = 'APPROVED', decision = 'ACCESS_GRANTED', decided_at = ?
                WHERE attempt_id = ? AND status = 'PENDING_EMAIL_APPROVAL' AND expires_at >= ?
                """, (now, attempt_id, now))

                if c.rowcount == 1:
                    return True, attempt_id, "APPROVED"
                return False, attempt_id, "ATTEMPT_ALREADY_DECIDED_OR_EXPIRED"

            # 2. Diagnosing failure
            c.execute("SELECT * FROM approval_links WHERE token_hash = ?", (token_hash,))
            row = c.fetchone()
            if not row:
                return False, None, "INVALID_TOKEN"
            if row["used_at"] is not None:
                return False, row["attempt_id"], "ALREADY_USED"
            if now > row["expires_at"]:
                return False, row["attempt_id"], "EXPIRED"

            return False, row["attempt_id"], "FAILED"

    # --- Audit Log ---
    def log_audit(self, event_type: str, outcome: str, attempt_id: Optional[str] = None, device_hash: Optional[str] = None, card_hash: Optional[str] = None, metadata: Optional[Dict[str, Any]] = None):
        meta_str = json.dumps(metadata or {})
        with get_db_cursor(self.db_path) as c:
            c.execute("""
            INSERT INTO audit_events (timestamp, attempt_id, device_hash, card_hash, event_type, outcome, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (time.time(), attempt_id, device_hash, card_hash, event_type, outcome, meta_str))

    def get_audit_events(
        self,
        attempt_id: Optional[str] = None,
        event_type: Optional[str] = None,
        device_hash: Optional[str] = None,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        query = "SELECT * FROM audit_events WHERE 1=1"
        params: List[Any] = []
        if attempt_id:
            query += " AND attempt_id = ?"
            params.append(attempt_id)
        if event_type:
            query += " AND event_type = ?"
            params.append(event_type)
        if device_hash:
            query += " AND device_hash = ?"
            params.append(device_hash)
        query += " ORDER BY event_id DESC LIMIT ?"
        params.append(limit)

        with get_db_cursor(self.db_path) as c:
            c.execute(query, tuple(params))
            results = []
            for row in c.fetchall():
                d = dict(row)
                d["metadata"] = json.loads(d["metadata_json"]) if d["metadata_json"] else {}
                results.append(d)
            return results

    # --- Generic Table Inspection for CLI / Viewer ---
    def get_table_names(self) -> List[str]:
        with get_db_cursor(self.db_path) as c:
            c.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
            return [row["name"] for row in c.fetchall()]

    def get_table_count(self, table_name: str) -> int:
        if table_name not in self.get_table_names():
            raise ValueError(f"Unknown table: {table_name}")
        with get_db_cursor(self.db_path) as c:
            c.execute(f"SELECT COUNT(*) as cnt FROM {table_name}")
            return c.fetchone()["cnt"]

    def get_table_columns(self, table_name: str) -> List[str]:
        if table_name not in self.get_table_names():
            raise ValueError(f"Unknown table: {table_name}")
        with get_db_cursor(self.db_path) as c:
            c.execute(f"PRAGMA table_info({table_name})")
            return [row["name"] for row in c.fetchall()]

    def get_table_rows(self, table_name: str, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        if table_name not in self.get_table_names():
            raise ValueError(f"Unknown table: {table_name}")
        with get_db_cursor(self.db_path) as c:
            c.execute(f"SELECT * FROM {table_name} LIMIT ? OFFSET ?", (limit, offset))
            return [dict(r) for r in c.fetchall()]

    def reset_tables(self):
        """Clears all table contents (used for test isolation)."""
        with get_db_cursor(self.db_path) as c:
            c.execute("DELETE FROM audit_events;")
            c.execute("DELETE FROM approval_links;")
            c.execute("DELETE FROM access_attempts;")
            c.execute("DELETE FROM challenges;")
            c.execute("DELETE FROM jobs;")
            c.execute("DELETE FROM devices;")
            c.execute("DELETE FROM users;")


db = DatabaseManager()

