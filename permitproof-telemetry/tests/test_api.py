import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from uuid import uuid4
import pytest
from fastapi.testclient import TestClient
from contracts.schemas import Event
from server.app import create_app
from server.storage import Store

TOKEN = "test-token-" + "x" * 32
BASE = "/api/v1/devices/pi-001"


@pytest.fixture
def setup(tmp_path):
    people = json.loads((Path(__file__).resolve().parents[1] / "data/mock_people.json").read_text())
    store = Store(tmp_path / "store.json", people)
    client = TestClient(create_app(store, TOKEN, "pi-001"))
    client.headers["Authorization"] = f"Bearer {TOKEN}"
    with client:
        yield client, store


def event(kind="nfc_tapped", uid="DEMO-001", **changes):
    return {"event_id": str(uuid4()), "device_id": "pi-001", "observed_at_ms": time.time_ns() // 1_000_000,
            "kind": kind, "uid": uid if kind == "nfc_tapped" else None, "source": "mock", **changes}


def send(client, payload):
    return client.post(BASE + "/events", json=payload)


def test_workflow_and_duplicate_start(setup):
    client, _ = setup
    assert send(client, event()).status_code == 200
    start = event("button_pressed")
    assert send(client, start).status_code == 200
    assert send(client, start).json()["duplicate"] is True
    assert client.get(BASE + "/desired-state").json()["phase"] == "active"
    assert client.get(BASE + "/status").json()["accepted_event_count"] == 2
    assert send(client, event("button_pressed")).status_code == 200
    assert client.get(BASE + "/desired-state").json()["phase"] == "complete"


@pytest.mark.parametrize("uid", ["UNKNOWN", "DEMO-002", "DEMO-003"])
def test_unknown_or_disallowed_role(setup, uid):
    client, _ = setup
    send(client, event(uid=uid))
    assert client.get(BASE + "/desired-state").json()["phase"] == "denied"
    send(client, event("button_pressed"))
    assert client.get(BASE + "/desired-state").json()["phase"] != "active"


def test_unknown_clears_person(setup):
    client, _ = setup
    send(client, event())
    send(client, event(uid="UNKNOWN"))
    assert client.get(BASE + "/desired-state").json()["person"] is None


def test_active_person_cannot_be_replaced_or_reset(setup):
    client, _ = setup
    send(client, event())
    send(client, event("button_pressed"))
    before = client.get(BASE + "/desired-state").json()
    send(client, event(uid="DEMO-003"))
    send(client, event("session_reset"))
    after = client.get(BASE + "/desired-state").json()
    assert after["phase"] == "active"
    assert after["person"] == before["person"]
    assert after["session_id"] == before["session_id"]


def test_conflicting_replay(setup):
    client, _ = setup
    original = event()
    send(client, original)
    assert send(client, {**original, "uid": "DEMO-003"}).status_code == 409


def test_auth_and_device_binding(setup):
    client, _ = setup
    assert client.get(BASE + "/status", headers={"Authorization": "Bearer wrong"}).status_code == 401
    assert client.get("/api/v1/devices/other/status").status_code == 403
    assert send(client, event(device_id="other")).status_code == 403


def test_reject_role_injection_and_bad_types(setup):
    client, _ = setup
    assert send(client, event(role="Supervisor")).status_code == 422
    assert send(client, event(observed_at_ms="123")).status_code == 422
    assert send(client, event(event_id="not-a-uuid")).status_code == 422


@pytest.mark.parametrize("offset", [-600000, 60000])
def test_timing_window(setup, offset):
    client, _ = setup
    assert send(client, event(observed_at_ms=time.time_ns() // 1_000_000 + offset)).status_code == 422


def test_report_revision(setup):
    client, _ = setup
    send(client, event())
    report = {"device_id": "pi-001", "revision": 1, "outputs": "mock", "applied": True,
              "observed_at_ms": time.time_ns() // 1_000_000, "lcd_backend": "console"}
    assert client.post(BASE + "/reported-state", json=report).status_code == 200
    assert client.post(BASE + "/reported-state", json={**report, "revision": 0}).status_code == 409
    assert client.post(BASE + "/reported-state", json={**report, "error": "broken"}).status_code == 422


def test_size_limit(setup):
    client, _ = setup
    assert client.post(BASE + "/events", content=b"x" * 9000).status_code == 413


def test_persistence_and_parallel_deduplication(setup):
    _, store = setup
    payload = Event.model_validate(event())
    with ThreadPoolExecutor(max_workers=8) as pool:
        receipts = list(pool.map(lambda _: store.event(payload), range(20)))
    assert sum(not x["duplicate"] for x in receipts) == 1
    reopened = Store(store.path, store.people)
    assert reopened.event(payload)["duplicate"] is True
    assert reopened.desired("pi-001").phase == "ready"


def test_failed_disk_commit_does_not_ack_or_mutate(setup, monkeypatch):
    _, store = setup
    def fail(_):
        raise OSError("disk full")
    monkeypatch.setattr(store, "_commit", fail)
    with pytest.raises(OSError):
        store.event(Event.model_validate(event()))
    assert store.desired("pi-001").revision == 0
    assert store.data["events"] == {}
