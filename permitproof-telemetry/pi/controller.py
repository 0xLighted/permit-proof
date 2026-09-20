import time
from uuid import uuid4
from contracts.schemas import DesiredState


class Controller:
    def __init__(self, api, hardware):
        self.api, self.hardware = api, hardware
        self.pending = None
        self.revision = None
        self.last_event = None

    def sync(self):
        state = DesiredState.model_validate(self.api.desired())
        if state.device_id != self.api.device_id:
            raise ValueError("Wrong device in server response")
        if self.revision is not None and state.revision < self.revision:
            raise ValueError("Server revision decreased; investigate state rollback")
        if state.revision != self.revision:
            try:
                self.hardware.apply(state)
            except Exception as exc:
                self.revision = None
                try:
                    self.api.report({"device_id": self.api.device_id, "revision": state.revision,
                                     "outputs": "hardware" if self.hardware.real else "mock",
                                     "lcd_backend": self.hardware.display.backend,
                                     "applied": False, "error": f"Output failure: {type(exc).__name__}",
                                     "observed_at_ms": time.time_ns() // 1_000_000})
                except Exception:
                    pass  # Preserve the original output error if reporting also fails.
                raise
            print(f"[STATE] {state.phase}, revision {state.revision}; MOCK workflow", flush=True)
        self.api.report({"device_id": self.api.device_id, "revision": state.revision,
                         "outputs": "hardware" if self.hardware.real else "mock",
                         "lcd_backend": self.hardware.display.backend,
                         "applied": True, "observed_at_ms": time.time_ns() // 1_000_000})
        self.revision = state.revision
        return state

    def emit(self, kind, uid=None):
        if self.pending is not None:
            print("A request is unresolved. Use retry; do not create a second action.")
            return
        event = {"event_id": str(uuid4()), "device_id": self.api.device_id,
                 "observed_at_ms": time.time_ns() // 1_000_000,
                 "source": "hardware" if self.hardware.real else "mock", "kind": kind, "uid": uid}
        self.pending = event
        self.retry()

    def retry(self):
        if self.pending is not None:
            receipt = self.api.event(self.pending)
            if receipt["event_id"] != self.pending["event_id"]:
                raise ValueError("Mismatched event receipt")
            self.last_event = self.pending
            self.pending = None
            print(f"[POST receipt] {receipt['decision']}; duplicate={receipt['duplicate']}", flush=True)
        self.sync()

    def offline(self):
        self.revision = None  # Reapply last confirmed state after reconnect, not just print it.
        self.hardware.offline()
