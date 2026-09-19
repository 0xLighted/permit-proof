import pytest
from fastapi.testclient import TestClient
from server import app, telemetry_history

client = TestClient(app)

@pytest.fixture(autouse=True)
def clear_history():
    """Clear in-memory telemetry before each test for test isolation."""
    telemetry_history.clear()
    yield
    telemetry_history.clear()


def test_root_endpoint():
    """Verify that the healthcheck/root endpoint is responding."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ONLINE"
    assert data["stage"] == "Stage 1 - Connectivity"
    assert "total_records_received" in data


def test_post_valid_telemetry():
    """Verify normal telemetry ingestion and terminal output triggers."""
    payload = {
        "device_id": "charlie-pi-01",
        "timestamp": 1726720000.0,
        "seq": 1,
        "temperature": 48.5,
        "humidity": 55.2,
        "cpu_load": 18.0,
        "memory_usage": 35.4,
        "voltage": 5.12
    }
    response = client.post("/api/telemetry", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "SUCCESS"
    assert data["device_id"] == "charlie-pi-01"
    assert data["seq"] == 1


def test_post_minimal_telemetry():
    """Verify telemetry with only required fields is valid."""
    payload = {
        "device_id": "charlie-pi-01"
    }
    response = client.post("/api/telemetry", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["status"] == "SUCCESS"
    assert data["device_id"] == "charlie-pi-01"


def test_get_telemetry_history():
    """Verify GET /api/telemetry returns recent entries."""
    client.post("/api/telemetry", json={"device_id": "pi-1", "seq": 1, "temperature": 42.0})
    client.post("/api/telemetry", json={"device_id": "pi-1", "seq": 2, "temperature": 43.5})

    response = client.get("/api/telemetry")
    assert response.status_code == 200
    history = response.json()
    assert len(history) == 2
    assert history[0]["seq"] == 1
    assert history[1]["seq"] == 2
    assert history[1]["temperature"] == 43.5


def test_missing_device_id_validation():
    """Verify that omitting device_id is rejected by Pydantic with 422."""
    payload = {
        "temperature": 48.5,
        "humidity": 55.2
    }
    response = client.post("/api/telemetry", json=payload)
    assert response.status_code == 422
    errors = response.json()["detail"]
    assert any(err["loc"][-1] == "device_id" for err in errors)


def test_invalid_type_validation():
    """Verify that invalid field types (e.g. string for temperature) return 422."""
    payload = {
        "device_id": "charlie-pi-01",
        "temperature": "not-a-number"
    }
    response = client.post("/api/telemetry", json=payload)
    assert response.status_code == 422


def test_custom_extra_fields():
    """Verify extra sensor readings in the extra dictionary."""
    payload = {
        "device_id": "charlie-pi-01",
        "extra": {
            "pressure_hpa": 1013.25,
            "air_quality_index": 45,
            "motion_detected": True
        }
    }
    response = client.post("/api/telemetry", json=payload)
    assert response.status_code == 201
    history_res = client.get("/api/telemetry")
    saved = history_res.json()[0]
    assert saved["extra"]["pressure_hpa"] == 1013.25
    assert saved["extra"]["motion_detected"] is True
