from contracts.schemas import DesiredState
from pi.controller import Controller
from pi.hardware import Hardware


class FakeAPI:
    device_id = "pi-001"
    def __init__(self):
        self.calls, self.reports = [], []
    def event(self, event):
        self.calls.append(event.copy())
        if len(self.calls) == 1:
            raise TimeoutError("receipt lost")
        return {"event_id": event["event_id"], "decision": "accepted", "duplicate": True}
    def desired(self):
        return DesiredState(device_id=self.device_id, revision=1).model_dump()
    def report(self, report):
        self.reports.append(report)


def test_retry_reuses_id_and_mock_never_loads_gpio():
    import sys
    api = FakeAPI()
    hardware = Hardware()
    controller = Controller(api, hardware)
    try:
        controller.emit("nfc_tapped", "DEMO-001")
    except TimeoutError:
        pass
    assert controller.pending is not None
    controller.retry()
    assert api.calls[0] == api.calls[1]
    assert controller.pending is None
    assert api.reports[-1]["outputs"] == "mock"
    assert "gpiozero" not in sys.modules
    assert "board" not in sys.modules


def test_output_failure_never_reports_success():
    import pytest
    api = FakeAPI()
    hardware = Hardware()
    def fail_apply(state):
        raise OSError("output unavailable")
    hardware.apply = fail_apply
    controller = Controller(api, hardware)
    with pytest.raises(OSError):
        controller.sync()
    assert controller.revision is None
    assert api.reports[-1]["applied"] is False
    assert api.reports[-1]["error"] == "Output failure: OSError"
