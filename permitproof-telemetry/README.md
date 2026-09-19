# PermitProof Telemetry

**Stage 1 — Telemetry Prototype (Mock Mode)**

**Start here. No soldered NFC reader, Pi connection, LEDs or LCD are needed in mock mode.**

This folder implements the agreed first milestone: NFC/person lookup, button start/completion requests, desired LED/LCD state, HTTP GET/POST, and reported application state. It is a local development lab, **not the final zero-trust system**. It does not authenticate a person from their card. Every approval is labelled `MOCK WORKFLOW`.

## Open and run in VS Code (Mac)

1. Open this folder (`permitproof-telemetry`) using **File → Open Folder**.
   If VS Code shows **Restricted Mode**, review the generated files and use **Manage → Trust** for this folder when ready to execute them. Do not trust the entire parent directory.
2. Open **Terminal → New Terminal**. This is your Mac terminal, not the Pi.
3. On a fresh copy, run:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m scripts.setup_local
```

If this workspace was already prepared by Codex, simply run `source .venv/bin/activate`.
The setup script generates a random lab token in `.env` without printing it. It never overwrites an existing `.env`.

4. Start the backend in terminal 1:

```bash
source .venv/bin/activate
python -m server.app
```

5. Open a **second** VS Code terminal and run:

```bash
source .venv/bin/activate
python -m pi.main
```

6. At the `mock>` prompt, enter one command at a time:

```text
tap DEMO-001
press
replay
press
status
tap UNKNOWN
reset
quit
```

Expected: recognised demo technician → start → duplicate suppressed (still active) → completion → report → unknown card denied → idle. LED and LCD actions are printed and labelled **MOCK**. `DEMO-002` is a supervisor identifier and `DEMO-003` a visitor: neither may act as the technician in this mock policy.

To run a short automated HTTP demonstration instead:

```bash
python -m scripts.demo
```

This generates additional demo events. It refuses to reset an active inspection. Finish one with `press` first.

Stop a process with Ctrl+C. Opening files does not execute hardware commands.

## VS Code run buttons

Install the Microsoft Python/Python Debugger extensions if not already available. Use **Python: Select Interpreter** to select `.venv`. Under **Run and Debug**, choose:

- **1 — Local mock API** (start first).
- **2 — Mock NFC and button console** (run alongside the API).
- **3 — Automated GET POST demo (API running)**.

These configurations never enable hardware. The Test Explorer can run `tests/`.

## What the files do

| Folder/file | Purpose |
|---|---|
| `server/app.py` | FastAPI HTTP routes, bearer-token/device checks, payload-size limit |
| `server/workflow.py` | Recognise demo person, deny unknown/disallowed roles, start/complete transitions |
| `server/storage.py` | Atomic JSON file replacement, persistent deduplication and state |
| `contracts/schemas.py` | Strict input/output fields, epoch milliseconds, source labels |
| `pi/main.py` | Interactive mock console or explicitly enabled real hardware loop |
| `pi/controller.py` | POST event → GET desired state → apply outputs → POST report |
| `pi/api_client.py` | HTTP transport, authentication, timeouts, loopback-only plain HTTP |
| `pi/nfc.py` | Real PN532 SPI adapter, GPIO5 chip select, duplicate-tap suppression |
| `pi/button.py` | Real GPIO25 button, pull-up and debounce |
| `pi/leds.py` | Mock printout and real one-colour-at-a-time outputs |
| `pi/display.py` | Mock 16×2 pages and opt-in real I²C LCD page rotation |
| `pi/hardware.py` | Resource creation/cleanup; default mode imports no GPIO libraries |
| `pi/pins.py` | Single source of truth for GPIO mapping |
| `data/mock_people.json` | Fictional UID/name/role lookup, loaded when server starts |
| `scripts/setup_local.py` | Local token/environment setup |
| `scripts/demo.py` | Repeatable HTTP smoke test |
| `tests/` | Workflow, auth, duplicate/retry, persistence and failure checks |
| `.vscode/` | Run/debug and test settings |
| `docs/` | API, fixed pin mapping, and later Pi workflow |

## Flow and colours

```text
Mock tap / real NFC → POST event → mock policy → desired revision stored
Pi agent           ← GET desired LED/LCD/person state
Pi agent           → apply outputs → POST reported revision
```

| Colour | Number 1 meaning |
|---|---|
| White | Ready for a card |
| Blue | Sending a local interaction |
| Green | Mock person allowed / mock inspection active / complete (LCD tells which) |
| Yellow | Scan required or communication unconfirmed |
| Red | Unknown/disallowed card |

An active session cannot be reassigned by tapping another card. Additional button actions are blocked while an earlier request is unresolved. Repeated POST of an identical event does not transition twice. Reusing its ID with changed content returns 409.

## API and storage

Local health: http://127.0.0.1:8000/health

API documentation: http://127.0.0.1:8000/docs (Swagger assets may require internet).

The client automatically reads the token from `.env`; no copying of secrets is necessary for the normal demo. All device routes require it. See `docs/api.md`.

Number 1 uses `runtime/mock-store.json` so it can run immediately without database installation. **PostgreSQL remains the production target, not implemented here.** Use exactly **one API process**, no multi-worker deployment. The lab store caps at 10,000 events; it is not designed for large load or an adversarial public network. No deletion/reset endpoint is exposed. `reset` changes the idle workflow only; it does not delete evidence.

## Tests

```bash
source .venv/bin/activate
python -m pytest -q
```

Tests use temporary stores and do not delete or change the demonstration's saved history. `requirements.lock.txt`, if present, records the tested local dependency versions. Use it for a repeatable install; the optional Pi packages require separate validation on the Pi.

See `docs/test-results.md` for the completed local checks and their limits.

## Offline behaviour and honest limits

- Mock console syncs when you issue a command; it is not a continuously monitored dashboard.
- Real mode polls every two seconds when healthy. Network timeouts are bounded, but hardware failure detection is not safety certified.
- Failed/uncertain POST keeps the same event in memory. `retry` reuses its ID and checks the server state. Do not claim success until a response arrives.
- Pending requests are **not persisted on the client** in Number 1. Do not quit the client while a start/completion request is unresolved; reconnect and inspect server status if it happens.
- New requests older than five minutes or more than thirty seconds in the future are rejected. A stale rejected request requires investigation/restart, not an altered timestamp on the same ID.
- No offline sensor queue, cryptographic signatures, expiring permits, passkeys, production RBAC, MQTT, hardware watchdog, or database administrator protection is implemented yet.
- A real adapter failure is an error, never silently presented as mock success.
- `applied` confirms software execution; it cannot prove an LED physically lit. `lcd_backend: console` explicitly means the real LCD was not used.
- Persisted mock sessions may still say `active` after a restart. This is not real authorisation and must not control machinery. Production must start unauthorised and obtain a fresh permit.

Do not expose this API directly to the hackathon network. It binds to localhost. Use an SSH tunnel for preliminary remote testing; hardened HTTPS/mTLS deployment is a later milestone.

## Hardware later

Read `docs/wiring.md` and `docs/vscode-and-pi.md`. Do not start real mode until the PN532 header is soldered and all GPIO/resistor connections are verified. LCD defaults to console output even in hardware mode.

Primary references: [PN532 driver](https://docs.circuitpython.org/projects/pn532/en/latest/examples.html), [FastAPI testing](https://fastapi.tiangolo.com/tutorial/testing/), [VS Code Python debugging](https://code.visualstudio.com/docs/python/debugging).
