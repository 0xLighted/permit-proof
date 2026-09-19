"""
PermitProof - Stage 2 Test Suite
Tests challenge issuance, HMAC verification, anti-replay, pre-approved job matching,
held result polling, and email magic-link approval.
"""

import pytest
import time
from fastapi.testclient import TestClient

from server.main import app
from server.store import store
from server.crypto import (
    get_master_secret,
    derive_keys,
    compute_device_id_hash,
    compute_card_id_hash,
    compute_message_hmac
)

client = TestClient(app)

# Test Fixtures / Helpers
CANONICAL_PI_ID = "pi-server-room-001"
RAW_CARD_UID = b"\x04\xa2\xb3\xc4\xd5\xe6\xf7"


@pytest.fixture(autouse=True)
def setup_store():
    """Resets and seeds in-memory store before each test."""
    store.reset()

    master = get_master_secret()
    k_device, k_card, _ = derive_keys(master)

    device_hash = compute_device_id_hash(k_device, CANONICAL_PI_ID)
    card_hash = compute_card_id_hash(k_card, RAW_CARD_UID)

    # Seed registered device & user
    store.register_device(device_id_hash=device_hash, room_id="server-room-alpha")
    store.register_user(card_id_hash=card_hash, full_name="Jasmine Zurayn", email="j.zurayn@example.com", role="technician")

    # Seed pre-approved accepted job
    store.add_job(
        job_id="job-inspect-99",
        supervisor_id="sup-001",
        technician_id=card_hash,
        device_id_hash=device_hash,
        status="accepted",
        is_complete=0
    )

    yield {
        "device_hash": device_hash,
        "card_hash": card_hash,
        "master": master
    }

    store.reset()


def test_health_check():
    """Verify health endpoint responds with Stage 2 metadata."""
    res = client.get("/health")
    assert res.status_code == 200
    data = res.json()
    assert data["status"] == "ONLINE"
    assert "Stage 2" in data["stage"]


def test_challenge_success(setup_store):
    """Registered device obtains 30s single-use challenge nonce."""
    dev_hash = setup_store["device_hash"]
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


def make_signed_payload(setup_store, dev_hash=None, card_hash=None, nonce=None, override_hmac=None):
    dev = dev_hash or setup_store["device_hash"]
    card = card_hash or setup_store["card_hash"]
    if nonce is None:
        nonce = client.get(f"/api/v1/challenge?device_id_hash={dev}").json()["nonce"]
    if override_hmac is not None:
        hmac_val = override_hmac
    else:
        _, _, k_msg = derive_keys(setup_store["master"])
        hmac_val = compute_message_hmac(k_msg, dev, card, nonce)
    return {
        "device_id_hash": dev,
        "card_id_hash": card,
        "nonce": nonce,
        "message_hmac": hmac_val
    }


def test_valid_access_attempt(setup_store):
    """Legitimate card tap with pre-approved job succeeds with 202 Accepted."""
    res = client.post("/api/v1/access-attempts", json=make_signed_payload(setup_store))
    assert res.status_code == 202
    data = res.json()
    assert data["status"] == "PENDING_EMAIL_APPROVAL"
    assert "attempt_id" in data
    assert "result_token" in data
    assert data["expires_in_seconds"] == 120


def test_tampered_hmac_rejected(setup_store):
    """Tampering with HMAC or payload fields is rejected with 401."""
    payload = make_signed_payload(setup_store, override_hmac="f" * 64)
    res = client.post("/api/v1/access-attempts", json=payload)
    assert res.status_code == 401
    assert "HMAC verification failed" in res.json()["detail"]


def test_replay_attack_rejected(setup_store):
    """Submitting the exact same signed POST a second time is rejected with 409."""
    payload = make_signed_payload(setup_store)
    res1 = client.post("/api/v1/access-attempts", json=payload)
    assert res1.status_code == 202

    res2 = client.post("/api/v1/access-attempts", json=payload)
    assert res2.status_code == 409
    assert "consumed" in res2.json()["detail"].lower()


def test_expired_nonce_rejected(setup_store):
    """Submitting after the 30-second nonce expiry window is rejected with 400."""
    payload = make_signed_payload(setup_store)
    store.challenges[payload["nonce"]]["expires_at"] = time.time() - 5.0

    res = client.post("/api/v1/access-attempts", json=payload)
    assert res.status_code == 400
    assert "expired" in res.json()["detail"].lower()


def test_nonce_device_mismatch(setup_store):
    """Using a nonce issued for another device is rejected with 403."""
    other_dev_hash = "e" * 64
    store.register_device(other_dev_hash, room_id="room-beta")
    other_nonce = client.get(f"/api/v1/challenge?device_id_hash={other_dev_hash}").json()["nonce"]

    payload = make_signed_payload(setup_store, nonce=other_nonce)
    res = client.post("/api/v1/access-attempts", json=payload)
    assert res.status_code == 403
    assert "not issued for this device" in res.json()["detail"].lower()


def test_unregistered_card_rejected(setup_store):
    """Valid HMAC and device, but unknown card hash is rejected with 403."""
    payload = make_signed_payload(setup_store, card_hash="1" * 64)
    res = client.post("/api/v1/access-attempts", json=payload)
    assert res.status_code == 403
    assert "not registered" in res.json()["detail"].lower()


def test_no_accepted_job_rejected(setup_store):
    """Registered card without an accepted incomplete job is rejected with 403."""
    for job in store.jobs.values():
        job["is_complete"] = 1
        job["status"] = "completed"

    payload = make_signed_payload(setup_store)
    res = client.post("/api/v1/access-attempts", json=payload)
    assert res.status_code == 403
    assert "pre-approval failed" in res.json()["detail"].lower()


def test_held_result_and_email_approval(setup_store):
    """
    End-to-end access flow:
    1. Pi submits valid attempt -> receives attempt_id & result_token
    2. Email link is generated
    3. Browser requests GET /api/v1/approve?token=... -> approves attempt
    4. Pi checks result -> receives APPROVED & ACCESS_GRANTED
    """
    post_res = client.post("/api/v1/access-attempts", json=make_signed_payload(setup_store))
    assert post_res.status_code == 202
    attempt_id = post_res.json()["attempt_id"]
    result_token = post_res.json()["result_token"]

    email_token = list(store.raw_approval_tokens.keys())[0]

    # 2. Browser approves via email magic link
    approve_res = client.get(f"/api/v1/approve?token={email_token}")
    assert approve_res.status_code == 200
    assert "Access Approved!" in approve_res.text

    # 3. Pi queries held result
    result_res = client.get(
        f"/api/v1/access-attempts/{attempt_id}/result",
        headers={"Authorization": f"Bearer {result_token}"}
    )
    assert result_res.status_code == 200
    res_data = result_res.json()
    assert res_data["status"] == "APPROVED"
    assert res_data["decision"] == "ACCESS_GRANTED"


def test_email_token_reuse_rejected(setup_store):
    """Clicking an email magic link a second time fails."""
    post_res = client.post("/api/v1/access-attempts", json=make_signed_payload(setup_store))
    assert post_res.status_code == 202
    email_token = list(store.raw_approval_tokens.keys())[0]

    res1 = client.get(f"/api/v1/approve?token={email_token}")
    assert res1.status_code == 200

    res2 = client.get(f"/api/v1/approve?token={email_token}")
    assert res2.status_code == 400
    assert "ALREADY_USED" in res2.text


def test_held_result_unauthorized_token(setup_store):
    """Polling result with wrong or missing bearer token is rejected with 401."""
    post_res = client.post("/api/v1/access-attempts", json=make_signed_payload(setup_store))
    attempt_id = post_res.json()["attempt_id"]

    # Missing token
    res_no_auth = client.get(f"/api/v1/access-attempts/{attempt_id}/result")
    assert res_no_auth.status_code == 401

    # Wrong token
    res_bad_auth = client.get(
        f"/api/v1/access-attempts/{attempt_id}/result",
        headers={"Authorization": "Bearer wrong-token-value"}
    )
    assert res_bad_auth.status_code == 401

