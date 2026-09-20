"""
PermitProof - Stage 2 SQLite Database & API Gateway Test Suite
Verifies challenge issuance, HMAC verification, anti-replay, SQLite atomic transactions,
job pre-approval lifecycle (supervisor creation, technician acceptance),
held result polling, and email magic-link approval.
"""

import pytest
import time
import os
from fastapi.testclient import TestClient

# Set test database path before importing app/db
TEST_DB_PATH = "test_permitproof.db"
os.environ["DATABASE_PATH"] = TEST_DB_PATH
os.environ.setdefault("MASTER_SECRET", "abf913629a0e2ef8560e9af135e97fa436f965bc47b80c47e3d5c0b861c6cc52")

from server.main import app
from server.db import db
from server.email_service import email_service
from server.crypto import (
    get_master_secret,
    derive_keys,
    compute_device_id_hash,
    compute_card_id_hash,
    compute_message_hmac
)

client = TestClient(app)

CANONICAL_PI_ID = "pi-server-room-001"
RAW_CARD_UID = b"\x04\xa2\xb3\xc4\xd5\xe6\xf7"
SUPERVISOR_CARD_HASH = "s" * 64


@pytest.fixture(autouse=True)
def setup_test_db():
    """Initializes and resets SQLite tables before each test."""
    db.init_schema()
    db.reset_tables()
    email_service.clear_outbox()

    master = get_master_secret()
    k_device, k_card, _ = derive_keys(master)

    device_hash = compute_device_id_hash(k_device, CANONICAL_PI_ID)
    card_hash = compute_card_id_hash(k_card, RAW_CARD_UID)

    # 1. Seed supervisor & technician users
    db.upsert_user(SUPERVISOR_CARD_HASH, "Alice Supervisor", "supervisor@example.com", "supervisor")
    db.upsert_user(card_hash, "Jasmine Zurayn", "j.zurayn@example.com", "technician")

    # 2. Seed registered device
    db.upsert_device(device_id_hash=device_hash, room_id="server-room-alpha", active=1, display_name="Alpha Reader")

    # 3. Seed pre-approved job (created by supervisor, accepted by technician)
    job = db.create_job(
        job_id="job-inspect-99",
        supervisor_id=SUPERVISOR_CARD_HASH,
        technician_id=card_hash,
        device_id_hash=device_hash,
        tasks=["Check rack temperature", "Verify UPS battery status"]
    )
    db.update_job_status(job["job_id"], "accepted", technician_id=card_hash)

    yield {
        "device_hash": device_hash,
        "card_hash": card_hash,
        "supervisor_hash": SUPERVISOR_CARD_HASH,
        "job_id": job["job_id"],
        "master": master
    }

    db.reset_tables()
    # Clean up file after session if needed
    if os.path.exists(TEST_DB_PATH):
        try:
            os.remove(TEST_DB_PATH)
        except Exception:
            pass


def make_signed_payload(setup_test_db, dev_hash=None, card_hash=None, nonce=None, override_hmac=None):
    dev = dev_hash or setup_test_db["device_hash"]
    card = card_hash or setup_test_db["card_hash"]
    if nonce is None:
        nonce = client.get(f"/api/v1/challenge?device_id_hash={dev}").json()["nonce"]
    if override_hmac is not None:
        hmac_val = override_hmac
    else:
        _, _, k_msg = derive_keys(setup_test_db["master"])
        hmac_val = compute_message_hmac(k_msg, dev, card, nonce)
    return {
        "device_id_hash": dev,
        "card_id_hash": card,
        "nonce": nonce,
        "message_hmac": hmac_val
    }


# ==============================================================================
# Health & Challenge Tests
# ==============================================================================

def test_health_check():
    """Verify health endpoint responds with Stage 2 and SQLite metadata."""
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ONLINE"
    assert "Stage 2" in data["stage"]
    assert "SQLite" in data["database"]


def test_challenge_success(setup_test_db):
    """Registered device obtains 30s single-use challenge nonce stored in SQLite."""
    dev_hash = setup_test_db["device_hash"]
    res = client.get(f"/api/v1/challenge?device_id_hash={dev_hash}")
    assert res.status_code == 200
    data = res.json()
    assert "nonce" in data
    assert len(data["nonce"]) > 10
    assert data["expires_in_seconds"] == 30


def test_challenge_invalid_device_format():
    """Malformed device_id_hash (not 64-hex) returns 400."""
    res = client.get("/api/v1/challenge?device_id_hash=invalid-short-hash")
    assert res.status_code == 400


def test_challenge_unregistered_device():
    """Unknown 64-hex device receives 403 error without leaking info."""
    fake_device_hash = "0" * 64
    res = client.get(f"/api/v1/challenge?device_id_hash={fake_device_hash}")
    assert res.status_code == 403


# ==============================================================================
# Access Attempt Verification Tests
# ==============================================================================

def test_valid_access_attempt(setup_test_db):
    """Legitimate card tap with pre-approved job succeeds with 202 Accepted."""
    res = client.post("/api/v1/access-attempts", json=make_signed_payload(setup_test_db))
    assert res.status_code == 202
    data = res.json()
    assert data["status"] == "PENDING_EMAIL_APPROVAL"
    assert "attempt_id" in data
    assert "result_token" in data
    assert data["expires_in_seconds"] == 120


def test_tampered_hmac_rejected(setup_test_db):
    """Tampering with HMAC or payload fields is rejected with 401."""
    payload = make_signed_payload(setup_test_db, override_hmac="f" * 64)
    res = client.post("/api/v1/access-attempts", json=payload)
    assert res.status_code == 401
    assert "HMAC verification failed" in res.json()["detail"]


def test_replay_attack_rejected(setup_test_db):
    """Submitting the exact same signed POST a second time is rejected with 409 by SQLite atomic update."""
    payload = make_signed_payload(setup_test_db)
    res1 = client.post("/api/v1/access-attempts", json=payload)
    assert res1.status_code == 202

    res2 = client.post("/api/v1/access-attempts", json=payload)
    assert res2.status_code == 409
    assert "consumed" in res2.json()["detail"].lower()


def test_expired_nonce_rejected(setup_test_db):
    """Submitting after the 30-second nonce expiry window is rejected with 400."""
    payload = make_signed_payload(setup_test_db)
    # Force expiration in SQLite
    from server.db import get_db_cursor
    with get_db_cursor() as c:
        c.execute("UPDATE challenges SET expires_at = ? WHERE nonce = ?", (time.time() - 5.0, payload["nonce"]))

    res = client.post("/api/v1/access-attempts", json=payload)
    assert res.status_code == 400
    assert "expired" in res.json()["detail"].lower()


def test_nonce_device_mismatch(setup_test_db):
    """Using a nonce issued for another device is rejected with 403."""
    other_dev_hash = "e" * 64
    db.upsert_device(other_dev_hash, room_id="room-beta")
    other_nonce = client.get(f"/api/v1/challenge?device_id_hash={other_dev_hash}").json()["nonce"]

    payload = make_signed_payload(setup_test_db, nonce=other_nonce)
    res = client.post("/api/v1/access-attempts", json=payload)
    assert res.status_code == 403
    assert "not issued for this device" in res.json()["detail"].lower()


def test_unregistered_card_rejected(setup_test_db):
    """Valid HMAC and device, but unknown card hash is rejected with 403."""
    payload = make_signed_payload(setup_test_db, card_hash="1" * 64)
    res = client.post("/api/v1/access-attempts", json=payload)
    assert res.status_code == 403
    assert "not registered" in res.json()["detail"].lower()


def test_no_accepted_job_rejected(setup_test_db):
    """Registered card without an accepted incomplete job is rejected with 403."""
    db.update_job_status(setup_test_db["job_id"], "completed")

    payload = make_signed_payload(setup_test_db)
    res = client.post("/api/v1/access-attempts", json=payload)
    assert res.status_code == 403
    assert "pre-approval failed" in res.json()["detail"].lower()


# ==============================================================================
# Held Result & Email Magic-Link Tests
# ==============================================================================

def test_held_result_and_email_approval(setup_test_db):
    """
    End-to-end access flow backed by SQLite:
    1. Pi submits valid attempt -> receives attempt_id & result_token
    2. Email link is generated in SQLite
    3. Browser requests GET /api/v1/approve?token=... -> approves attempt
    4. Pi checks result -> receives APPROVED & ACCESS_GRANTED
    """
    post_res = client.post("/api/v1/access-attempts", json=make_signed_payload(setup_test_db))
    assert post_res.status_code == 202
    attempt_id = post_res.json()["attempt_id"]
    result_token = post_res.json()["result_token"]

    email_token = email_service.get_latest_token(attempt_id)
    assert email_token is not None

    # Browser approves via email magic link
    approve_res = client.get(f"/api/v1/approve?token={email_token}")
    assert approve_res.status_code == 200
    assert "Access Approved!" in approve_res.text

    # Pi queries held result
    result_res = client.get(
        f"/api/v1/access-attempts/{attempt_id}/result",
        headers={"Authorization": f"Bearer {result_token}"}
    )
    assert result_res.status_code == 200
    res_data = result_res.json()
    assert res_data["status"] == "APPROVED"
    assert res_data["decision"] == "ACCESS_GRANTED"
    assert res_data.get("grant_signature") is not None
    assert res_data.get("grant_expires_at") is not None
    assert res_data["grant_expires_at"] > time.time()


def test_email_token_reuse_rejected(setup_test_db):
    """Clicking an email magic link a second time fails."""
    post_res = client.post("/api/v1/access-attempts", json=make_signed_payload(setup_test_db))
    assert post_res.status_code == 202
    attempt_id = post_res.json()["attempt_id"]
    email_token = email_service.get_latest_token(attempt_id)

    # First click: OK
    res1 = client.get(f"/api/v1/approve?token={email_token}")
    assert res1.status_code == 200

    # Second click: Rejected
    res2 = client.get(f"/api/v1/approve?token={email_token}")
    assert res2.status_code == 400
    assert "ALREADY_USED" in res2.text


def test_grant_signature_validation_and_replay_protection(setup_test_db):
    """Verifies that the success grant HMAC signature, expiration, and replay protection work."""
    from server.crypto import derive_result_key, verify_grant_signature, compute_grant_signature

    post_res = client.post("/api/v1/access-attempts", json=make_signed_payload(setup_test_db))
    assert post_res.status_code == 202
    attempt_id = post_res.json()["attempt_id"]
    result_token = post_res.json()["result_token"]
    email_token = email_service.get_latest_token(attempt_id)

    client.get(f"/api/v1/approve?token={email_token}")

    result_res = client.get(
        f"/api/v1/access-attempts/{attempt_id}/result",
        headers={"Authorization": f"Bearer {result_token}"}
    )
    assert result_res.status_code == 200
    data = result_res.json()

    k_res = derive_result_key(setup_test_db["master"])
    dev_hash = setup_test_db["device_hash"]

    # 1. Valid signature and unexpired
    valid, reason = verify_grant_signature(
        k_res=k_res,
        attempt_id=attempt_id,
        device_id_hash=dev_hash,
        decision="ACCESS_GRANTED",
        expires_at=data["grant_expires_at"],
        signature=data["grant_signature"]
    )
    assert valid is True
    assert reason == "VALID"

    # 2. Replay with expired timestamp rejected
    valid_expired, reason_expired = verify_grant_signature(
        k_res=k_res,
        attempt_id=attempt_id,
        device_id_hash=dev_hash,
        decision="ACCESS_GRANTED",
        expires_at=int(time.time()) - 5,
        signature=compute_grant_signature(k_res, attempt_id, dev_hash, "ACCESS_GRANTED", int(time.time()) - 5)
    )
    assert valid_expired is False
    assert reason_expired == "GRANT_EXPIRED"

    # 3. Replay against different device rejected
    diff_device = "f" * 64
    valid_dev, reason_dev = verify_grant_signature(
        k_res=k_res,
        attempt_id=attempt_id,
        device_id_hash=diff_device,
        decision="ACCESS_GRANTED",
        expires_at=data["grant_expires_at"],
        signature=data["grant_signature"]
    )
    assert valid_dev is False
    assert reason_dev == "SIGNATURE_MISMATCH"

    # 4. Tampered decision rejected
    valid_tamper, reason_tamper = verify_grant_signature(
        k_res=k_res,
        attempt_id=attempt_id,
        device_id_hash=dev_hash,
        decision="TAMPERED_GRANTED",
        expires_at=data["grant_expires_at"],
        signature=data["grant_signature"]
    )
    assert valid_tamper is False
    assert reason_tamper == "SIGNATURE_MISMATCH"


def test_held_result_unauthorized_token(setup_test_db):
    """Polling result with wrong or missing bearer token is rejected with 401."""
    post_res = client.post("/api/v1/access-attempts", json=make_signed_payload(setup_test_db))
    attempt_id = post_res.json()["attempt_id"]

    # Missing token
    assert client.get(f"/api/v1/access-attempts/{attempt_id}/result").status_code == 401

    # Wrong token
    res_bad = client.get(
        f"/api/v1/access-attempts/{attempt_id}/result",
        headers={"Authorization": "Bearer wrong-token-value"}
    )
    assert res_bad.status_code == 401


# ==============================================================================
# Job Pre-Approval API Gateway Workflow Tests
# ==============================================================================

def test_supervisor_create_and_technician_accept_job(setup_test_db):
    """Tests the full web pre-approval job workflow."""
    sup_hash = setup_test_db["supervisor_hash"]
    tech_hash = setup_test_db["card_hash"]
    dev_hash = setup_test_db["device_hash"]

    # 1. Supervisor creates new job
    create_res = client.post("/api/v1/jobs", json={
        "supervisor_id": sup_hash,
        "technician_id": tech_hash,
        "device_id_hash": dev_hash,
        "tasks": ["Inspect server rack A", "Replace air filter"]
    })
    assert create_res.status_code == 201
    job_id = create_res.json()["job_id"]
    assert create_res.json()["status"] == "pending"

    # 2. Technician lists jobs
    list_res = client.get(f"/api/v1/jobs?technician_id={tech_hash}")
    assert list_res.status_code == 200
    jobs = list_res.json()
    assert any(j["job_id"] == job_id for j in jobs)

    # 3. Technician accepts job -> becomes active pre-approval
    accept_res = client.post(f"/api/v1/jobs/{job_id}/accept", json={"technician_id": tech_hash})
    assert accept_res.status_code == 200
    assert accept_res.json()["job_status"] == "accepted"


def test_technician_cannot_create_job(setup_test_db):
    """Only supervisors can create pre-approval jobs."""
    tech_hash = setup_test_db["card_hash"]
    dev_hash = setup_test_db["device_hash"]

    res = client.post("/api/v1/jobs", json={
        "supervisor_id": tech_hash,  # Technician tries to act as supervisor
        "technician_id": tech_hash,
        "device_id_hash": dev_hash,
        "tasks": ["Unauthorized self-approval"]
    })
    assert res.status_code == 403
    assert "Only supervisors" in res.json()["detail"]


# ==============================================================================
# Audit Trail & Zero-Trust Invariant Tests
# ==============================================================================

def test_audit_events_endpoint_and_token_privacy(setup_test_db):
    """
    Verifies that the audit log query endpoint works and that raw secrets
    (email token, result token, raw UID) are strictly omitted from SQLite audit metadata
    per STAGE2_HANDOFF.md line 157.
    """
    post_res = client.post("/api/v1/access-attempts", json=make_signed_payload(setup_test_db))
    assert post_res.status_code == 202
    attempt_id = post_res.json()["attempt_id"]
    result_token = post_res.json()["result_token"]
    email_token = email_service.get_latest_token(attempt_id)

    # Query audit events via API Gateway
    audit_res = client.get(f"/api/v1/audit-events?attempt_id={attempt_id}")
    assert audit_res.status_code == 200
    events = audit_res.json()
    assert len(events) >= 1

    for ev in events:
        meta = ev.get("metadata", {})
        # Zero-trust privacy assertion: raw secrets MUST NOT be logged
        assert "email_token" not in meta, "Leak detected: raw email_token found in audit metadata!"
        assert email_token not in str(meta), "Leak detected: raw email_token value found in audit string!"
        assert result_token not in str(meta), "Leak detected: raw result_token value found in audit string!"
        assert setup_test_db["master"].hex() not in str(meta), "Leak detected: master key found in audit!"


def test_maintenance_prune_challenges(setup_test_db):
    """Verifies challenge pruning removes expired nonces."""
    dev = setup_test_db["device_hash"]
    # Issue a challenge
    c_res = client.get(f"/api/v1/challenge?device_id_hash={dev}")
    assert c_res.status_code == 200

    # Prune challenges older than -1 seconds (forces prune of just created)
    prune_res = client.post("/api/v1/maintenance/prune-challenges?max_age_seconds=-100")
    assert prune_res.status_code == 200
    assert prune_res.json()["status"] == "SUCCESS"


def test_job_is_complete_constraint(setup_test_db):
    """
    Verifies that the SQLite schema CHECK constraint enforces is_complete=1
    if and only if status='completed'.
    """
    import sqlite3
    from server.db import get_db_cursor

    # Attempting to insert status='pending' with is_complete=1 should raise IntegrityError
    with pytest.raises(sqlite3.IntegrityError):
        with get_db_cursor() as c:
            c.execute("""
            INSERT INTO jobs (job_id, created_at, supervisor_id, technician_id, device_id_hash, tasks_json, status, is_complete)
            VALUES ('job-bad-state', 1000.0, ?, ?, ?, '[]', 'pending', 1)
            """, (setup_test_db["supervisor_hash"], setup_test_db["card_hash"], setup_test_db["device_hash"]))

