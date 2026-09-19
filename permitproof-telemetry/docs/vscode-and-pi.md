# VS Code now, Raspberry Pi later

## Now: your Mac

Open `permitproof-telemetry` in VS Code, select its `.venv` interpreter, and follow README. This does not use your existing Pi SSH terminal or install anything on the Pi. Hardware code stays dormant by default. Local files live in the project workspace on the Mac, not on the Pi.

## Later: put the project on the Pi

Copy the source folder using an SSH file-transfer tool or Git. Do not copy `.venv`, `.env`, `runtime`, caches, or private credentials. The Mac virtual environment cannot be reused on Linux. Keep a backup of the source outside the Pi's SD card.

In VS Code install Microsoft's **Remote - SSH** extension. Open the Command Palette → **Remote-SSH: Connect to Host** → `charlie_pi@charlie-pi.local` (or the verified Pi IP). Verify the host fingerprint when establishing trust; use your existing credentials without posting them in chat. Open the folder you copied. The lower-left remote indicator should identify the Pi, and the integrated terminal then runs on the Pi.

On the Pi, from the project folder:

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip python3-lgpio python3-gpiozero
python3 -m venv --system-site-packages .venv
source .venv/bin/activate
python -m pip install -r requirements-pi.txt
python -m scripts.setup_local
```

Enable SPI using `sudo raspi-config` and verify `/dev/spidev0.0`. Local server and mock client can first run together on the Pi with the same commands as on the Mac.

After soldering and checking every connection in `wiring.md`, start the local API in one terminal, and in another:

```bash
source .venv/bin/activate
python -m pi.main --hardware --confirm-wiring
```

This activates NFC, all five LEDs and the button. **Do not run if those circuits are not checked.** LCD stays a console simulation. Real adapter exceptions stop rather than falling back to fake success. Actual card UIDs are printed; add their exact uppercase colon-separated values as keys in `data/mock_people.json` using fictional person records, then restart the API. Never treat the UID as secure authentication.

The optional LCD is only enabled after its electrical connection and address are verified:

```bash
python -m pi.main --hardware --confirm-wiring --lcd
```

This also requires the explicit `.env` opt-in documented in wiring.md. The code is written, but real drivers must still be tested on your hardware. Green LED means only the mock workflow's state.

## Later: backend on the assigned VM

Deploy the source on that VM, install its backend requirements, and generate a separate private lab token. Configure the Pi client to use that token securely. Keep the API bound to loopback for this milestone. An SSH tunnel from the Pi can forward `127.0.0.1:8000` to the VM's loopback API:

```text
ssh -N -L 8000:127.0.0.1:8000 YOUR_VM_USER@YOUR_VERIFIED_VM_IP
```

Use actual VM credentials, not the Pi username by assumption. If port 8000 is already occupied on the Pi, use another local port and change `PERMITPROOF_API_URL`. Do not start a second local API on the same port. Token provisioning is manual; do not send the secret in telemetry or commit it.

Production work remains: PostgreSQL transactional storage; human authentication and approval; unique device credentials; HTTPS/mTLS or MQTT; signed events/permits/receipts; durable device outbox; expiring authorisation; bounded load and audit logging. This folder is the Number 1 mock lab, not a completed production deployment.
