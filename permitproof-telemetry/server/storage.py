"""Single-process JSON lab store. PostgreSQL remains the production target."""
import copy
import hashlib
import json
import os
import tempfile
import threading
import time
from pathlib import Path
from contracts.schemas import DesiredState, Event, Report
from server.workflow import transition


class Conflict(Exception):
    pass


class StoreFull(Exception):
    pass


class Store:
    def __init__(self, path: Path, people: dict, max_events: int = 10000):
        self.path, self.people, self.max_events = path, people, max_events
        self.lock = threading.RLock()
        self.data = json.loads(path.read_text()) if path.exists() else {"events": {}, "states": {}, "reports": {}}

    def _commit(self, data):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fd, name = tempfile.mkstemp(dir=self.path.parent, prefix=".store-", suffix=".tmp")
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(data, f, ensure_ascii=True)
                f.flush()
                os.fsync(f.fileno())
            os.replace(name, self.path)
        finally:
            if os.path.exists(name):
                os.unlink(name)
        self.data = data

    def desired(self, device_id):
        with self.lock:
            return DesiredState.model_validate(self.data["states"].get(device_id, {"device_id": device_id}))

    def event(self, event: Event):
        digest = hashlib.sha256(json.dumps(event.model_dump(), sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        key = f"{event.device_id}:{event.event_id}"
        with self.lock:
            existing = self.data["events"].get(key)
            if existing:
                if existing["digest"] != digest:
                    raise Conflict("Event ID already used with different content")
                return {**existing["receipt"], "duplicate": True}
            if len(self.data["events"]) >= self.max_events:
                raise StoreFull("Lab event capacity reached; export data before starting a new lab store")
            now = time.time_ns() // 1_000_000
            # Number 1 has no offline upload queue: reject very old/future new requests.
            if not now - 300000 <= event.observed_at_ms <= now + 30000:
                raise ValueError("New request timestamp outside lab window (-5 min / +30 sec)")
            state, decision = transition(self.desired(event.device_id), event, self.people)
            receipt = {"event_id": event.event_id, "revision": state.revision,
                       "received_at_ms": now, "decision": decision, "duplicate": False, "workflow_mode": "mock"}
            data = copy.deepcopy(self.data)
            data["events"][key] = {"digest": digest, "event": event.model_dump(), "receipt": receipt}
            data["states"][event.device_id] = state.model_dump()
            self._commit(data)
            return receipt

    def report(self, report: Report):
        with self.lock:
            state = self.desired(report.device_id)
            if report.revision != state.revision:
                raise Conflict("Report must match the current desired revision; GET state again")
            data = copy.deepcopy(self.data)
            data["reports"][report.device_id] = {**report.model_dump(), "received_at_ms": time.time_ns() // 1_000_000}
            self._commit(data)

    def status(self, device_id):
        with self.lock:
            relevant = [x for x in self.data["events"].values() if x["event"]["device_id"] == device_id]
            return {"desired": self.desired(device_id).model_dump(),
                    "reported": copy.deepcopy(self.data["reports"].get(device_id)),
                    "accepted_event_count": len(relevant),
                    "recent_events": copy.deepcopy(relevant[-10:]),
                    "storage": "JSON lab store; single process", "workflow_mode": "mock"}
