"""
PermitProof - Frontend Bridge & Dashboard Integration Test Suite
Verifies GET /api/state, POST /api/action (lifecycle: accept, tap, magic link approval,
checklist, complete, create, revoke), GET /api/audit-log, and SPA routes.
"""

import pytest
import os
from fastapi.testclient import TestClient

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
    compute_card_id_hash
)

client = TestClient(app)

CANONICAL_PI_ID = "pi-server-room-001"
RAW_CARD_UID = b"\x04\xa2\xb3\xc4\xd5\xe6\xf7"
SUPERVISOR_CARD_HASH = "s" * 64


@pytest.fixture(autouse=True)
def setup_bridge_db():
    db.init_schema()
    db.reset_tables()
    email_service.clear_outbox()

    master = get_master_secret()
    k_device, k_card, _ = derive_keys(master)
    dev_hash = compute_device_id_hash(k_device, CANONICAL_PI_ID)
    tech_hash = compute_card_id_hash(k_card, RAW_CARD_UID)

    db.upsert_user(SUPERVISOR_CARD_HASH, "Alice Supervisor", "supervisor@example.com", "supervisor")
    db.upsert_user(tech_hash, "Jasmine Zurayn", "technician@example.com", "technician")
    db.upsert_device(dev_hash, "server-room-alpha", active=1, display_name="Alpha Reader")

    job_data = db.create_job(
        job_id="job-test-bridge",
        supervisor_id=SUPERVISOR_CARD_HASH,
        technician_id=tech_hash,
        device_id_hash=dev_hash,
        tasks=["Check rack cooling fans", "Verify physical tamper wire"]
    )

    return {
        "dev_hash": dev_hash,
        "tech_hash": tech_hash,
        "job_id": job_data["job_id"]
    }


def test_technician_state_lifecycle(setup_bridge_db):
    """Verifies technician state fetching and job pre-approval accept."""
    res = client.get("/api/state?role=technician")
    assert res.status_code == 200
    data = res.json()
    assert data["role"] == "technician"
    assert data["technician"] == "Jasmine Zurayn"
    assert len(data["tasks"]) == 1
    task = data["tasks"][0]
    assert task["id"] == "job-test-bridge"
    assert task["status"] == "assigned"
    assert data["auth_state"]["authenticated"] is False
    assert data["auth_state"]["otp_pending"] is False

    # Accept the job (pre-approval established)
    act_res = client.post("/api/action", json={"action": "accept", "id": "job-test-bridge"})
    assert act_res.status_code == 200
    state = act_res.json()
    assert state["tasks"][0]["status"] == "assigned"


def test_tap_and_magic_link_approval(setup_bridge_db):
    """Verifies tap triggers pending email approval, and magic link approves access."""
    # First accept job
    client.post("/api/action", json={"action": "accept", "id": "job-test-bridge"})

    # Simulate tap
    tap_res = client.post("/api/action", json={"action": "tap", "id": "job-test-bridge"})
    assert tap_res.status_code == 200
    tap_state = tap_res.json()
    assert tap_state["auth_state"]["otp_pending"] is True
    assert tap_state["auth_state"]["authenticated"] is False
    assert tap_state["tasks"][0]["status"] == "verifying"
    magic_link = tap_state["auth_state"]["magic_link_url"]
    assert magic_link is not None
    assert "/api/v1/approve?token=" in magic_link

    # Click magic link
    approve_res = client.get(magic_link)
    assert approve_res.status_code == 200
    assert "Access Approved" in approve_res.text

    # Verify technician state now shows authenticated and verified
    state_res = client.get("/api/state?role=technician")
    state = state_res.json()
    assert state["auth_state"]["authenticated"] is True
    assert state["auth_state"]["otp_pending"] is False
    assert state["tasks"][0]["status"] == "verified"


def test_checklist_and_complete(setup_bridge_db):
    """Verifies procedure checklist toggling and completing task."""
    # Accept and simulate tap + approve
    client.post("/api/action", json={"action": "accept", "id": "job-test-bridge"})
    tap_res = client.post("/api/action", json={"action": "tap", "id": "job-test-bridge"})
    magic_link = tap_res.json()["auth_state"]["magic_link_url"]
    client.get(magic_link)

    # Toggle checklist items
    cl1 = client.post("/api/action", json={"action": "checklist", "id": "job-test-bridge", "index": 0})
    assert cl1.status_code == 200
    assert cl1.json()["tasks"][0]["checklist"][0]["done"] is True

    cl2 = client.post("/api/action", json={"action": "checklist", "id": "job-test-bridge", "index": 1})
    assert cl2.status_code == 200
    assert cl2.json()["tasks"][0]["checklist"][1]["done"] is True

    # Complete work order
    comp_res = client.post("/api/action", json={"action": "complete", "id": "job-test-bridge"})
    assert comp_res.status_code == 200
    assert comp_res.json()["tasks"][0]["status"] == "completed"
    assert comp_res.json()["tasks"][0]["is_complete"] is True


def test_supervisor_state_and_actions(setup_bridge_db):
    """Verifies supervisor state view, permit creation, and permit revocation."""
    res = client.get("/api/state?role=supervisor")
    assert res.status_code == 200
    data = res.json()
    assert data["role"] == "supervisor"
    assert data["supervisor"] == "Alice Supervisor"
    assert len(data["tasks"]) == 1
    assert "events" in data
    assert len(data["technicians"]) >= 1

    # Supervisor creates new job
    create_res = client.post("/api/action", json={
        "action": "create",
        "title": "Emergency UPS Inspection",
        "room": "server-room-alpha",
        "tasks": ["Check battery cells"]
    })
    assert create_res.status_code == 200
    state = create_res.json()
    assert len(state["tasks"]) == 2

    # Supervisor revokes the new job
    new_job_id = state["tasks"][0]["id"]
    revoke_res = client.post("/api/action", json={"action": "revoke", "id": new_job_id})
    assert revoke_res.status_code == 200
    revoked_state = revoke_res.json()
    revoked_task = next(t for t in revoked_state["tasks"] if t["id"] == new_job_id)
    assert revoked_task["status"] == "revoked"


def test_audit_log_endpoint(setup_bridge_db):
    """Verifies GET /api/audit-log returns formatted records."""
    res = client.get("/api/audit-log")
    assert res.status_code == 200
    events = res.json()
    assert isinstance(events, list)


def test_spa_routes():
    """Verifies SPA root and dashboard routes serve the frontend application."""
    for path in ["/", "/technician", "/supervisor"]:
        res = client.get(path)
        assert res.status_code == 200
        assert "html" in res.headers.get("content-type", "").lower()
