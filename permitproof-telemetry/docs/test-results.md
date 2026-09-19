# Number 1 verification

Tested on this Mac on 2026-09-19 with Python 3.14.6. Dependency versions are recorded in `requirements.lock.txt`.

- `python -m pytest -q`: **17 passed**. Two upstream deprecation warnings from Starlette's test client; no test failures.
- Python compilation check of contracts, Pi adapters, server and scripts: passed.
- Live localhost HTTP demo: **PASS**. Checked unknown-card denial, fictional person lookup, start, duplicate suppression, completion, GET desired state and POST applied report.
- The test server was stopped after the demo. Start it from the README instructions.
- The mock store contains the demonstration events; they are fictional. No real person or sensor readings were sent.

Tests include missing/wrong credentials, wrong device, invalid/extra payload fields, stale/future epochs, changed duplicate content, simultaneous duplicate requests, saved state reload, failed persistence and output-error reporting.

Physical PN532, LED, button and LCD operation has **not** been verified. No code was deployed to the Pi or the organiser's VM. The Pi uses a different Python version and its optional drivers still need installation and on-device validation. These checks are development checks, not a production security audit.
