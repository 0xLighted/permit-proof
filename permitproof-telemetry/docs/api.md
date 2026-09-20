# Number 1 HTTP contract

`Authorization: Bearer <private local token>` is required on all `/api/v1/devices/…` routes. The token is scoped to the configured device ID. This is a lab credential, not a device certificate or a supervisor login.

| Method | Route | Purpose |
|---|---|---|
| GET | `/health` | Process health; no claim of physical hardware health |
| POST | `/api/v1/devices/pi-001/events` | NFC/button/mock reset event |
| GET | `/api/v1/devices/pi-001/desired-state` | LED colour and two-line LCD pages |
| POST | `/api/v1/devices/pi-001/reported-state` | Current revision applied/error, mock vs hardware output |
| GET | `/api/v1/devices/pi-001/status` | Desired/reported state and last ten accepted events |

Example event structure (use a current epoch timestamp and a new UUID in actual requests):

```json
{
  "event_id": "7849ae41-ff74-4f2d-8671-671b10cdf4f2",
  "device_id": "pi-001",
  "observed_at_ms": 1790000000000,
  "source": "mock",
  "kind": "nfc_tapped",
  "uid": "DEMO-001"
}
```

The client generates UUIDs/timestamps automatically. Button event kind is `button_pressed` and `uid` is null. Backend determines start versus completion from its current workflow state. Unknown fields, including caller-supplied roles, are rejected.

Event receipt: event ID, resulting revision, receipt epoch, decision, `duplicate`, and `workflow_mode: mock`. A receipt acknowledges file commit, not cryptographic authenticity. Retry identical events; do not regenerate the event ID after an uncertain response.

POST report fields: device ID, revision, outputs (`mock`/`hardware`), lcd_backend (`console`/`i2c`), applied boolean, observation epoch, optional error. Only the current desired revision may be reported. Server stores receipt time separately.

Status codes: 401 token missing/invalid; 403 device mismatch; 409 conflicting event or stale report; 413 body over 8 KiB; 422 invalid schema/time; 507 lab capacity reached. Unexpected storage failures produce a server error and no successful receipt. Do not treat HTTP success as industrial authorisation; all decisions remain mock.
