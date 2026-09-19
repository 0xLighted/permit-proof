# Number 1 verification

Tested on this Mac on 2026-09-19 with Python 3.14.6. Dependency versions are recorded in `requirements.lock.txt`.

- `python -m pytest -q`: **17 passed**. Two upstream deprecation warnings from Starlette's test client; no test failures.
- Python compilation check of contracts, Pi adapters, server and scripts: passed.
- Live localhost HTTP demo: **PASS**. Checked unknown-card denial, fictional person lookup, start, duplicate suppression, completion, GET desired state and POST applied report.
- The test server was stopped after the demo. Start it from the README instructions.
- The mock store contains the demonstration events; they are fictional. No real person or sensor readings were sent.

Tests include missing/wrong credentials, wrong device, invalid/extra payload fields, stale/future epochs, changed duplicate content, simultaneous duplicate requests, saved state reload, failed persistence and output-error reporting.

Hardware was subsequently verified on 2026-09-19 on a Raspberry Pi 5 Model B Rev 1.1 (2 GB):

- SPI0 loopback returned the exact transmitted bytes.
- The PN532 responded over SPI and reported firmware 1.6; real NFC card UIDs were read.
- All five GPIO LEDs illuminated individually and together through their 1 kOhm series resistors.
- The GPIO25 push button produced press and release events using the internal pull-up.
- The PCF8574 I2C LCD was detected at address `0x27` and displayed the application output while powered from 3.3 V.
- The local API and real Pi client ran together: NFC input reached the backend and the requested LED/LCD output was applied. The API must be started separately after a reboot.

This verifies the hackathon prototype wiring and application path. It is not a production security audit, and NFC UID lookup remains mock identification rather than cryptographic user authentication. The organiser's VM deployment has not yet been verified.
