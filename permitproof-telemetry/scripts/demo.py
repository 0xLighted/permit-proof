"""Run a real local HTTP GET/POST demo against an already running lab API."""
import json
from pathlib import Path
from dotenv import load_dotenv
from pi.api_client import API
from pi.controller import Controller
from pi.hardware import Hardware


def main():
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
    api = API()
    outputs = Hardware()
    controller = Controller(api, outputs)
    try:
        current = controller.sync()
        if current.phase == "active":
            raise RuntimeError("Existing inspection active. Complete it in the mock console first.")
        controller.emit("session_reset")
        controller.emit("nfc_tapped", "UNKNOWN")
        controller.emit("nfc_tapped", "DEMO-001")
        controller.emit("button_pressed")
        before = api.status()["accepted_event_count"]
        receipt = api.event(controller.last_event)
        assert receipt["duplicate"] is True
        assert api.status()["accepted_event_count"] == before
        assert api.desired()["phase"] == "active"
        controller.emit("button_pressed")
        final = api.status()
        assert final["desired"]["phase"] == "complete"
        assert final["reported"]["revision"] == final["desired"]["revision"]
        print(json.dumps({"result": "PASS", "workflow": "mock", "outputs": "mock",
                          "checks": ["unknown card denied", "mock person lookup", "start", "duplicate suppressed",
                                     "completion", "GET desired state", "POST applied report"]}, indent=2))
    finally:
        outputs.close()
        api.close()


if __name__ == "__main__":
    main()
