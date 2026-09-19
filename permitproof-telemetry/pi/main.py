"""Laptop mock CLI by default; --hardware --confirm-wiring enables real Pi IO."""
import argparse
import json
import time
from pathlib import Path
import httpx
from dotenv import load_dotenv
from pi.api_client import API
from pi.controller import Controller
from pi.hardware import Hardware

load_dotenv(Path(__file__).resolve().parents[1] / ".env")


def show_error(exc):
    if isinstance(exc, httpx.HTTPStatusError):
        print(f"API rejected request: {exc.response.status_code} {exc.response.text[:250]}")
    else:
        print(f"Connection/output error: {exc}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--hardware", action="store_true")
    parser.add_argument("--confirm-wiring", action="store_true")
    parser.add_argument("--lcd", action="store_true")
    args = parser.parse_args()
    if args.hardware and not args.confirm_wiring:
        parser.error("Hardware mode requires --confirm-wiring after checking docs/wiring.md")
    api = API()
    hardware = Hardware(real=args.hardware, lcd=args.lcd)
    controller = Controller(api, hardware)
    print("NUMBER 1 — MOCK AUTHORISATION POLICY. No signed permits or real user authentication.")
    try:
        try:
            controller.sync()
        except (httpx.HTTPError, ValueError, OSError) as exc:
            show_error(exc)
            controller.offline()
        if args.hardware:
            deadline = 0
            print("Hardware active. Ctrl+C stops and turns LEDs off.")
            while True:
                try:
                    if time.monotonic() >= deadline:
                        controller.retry()
                        deadline = time.monotonic() + 2
                    uid = hardware.nfc.poll()
                    if uid:
                        print(f"[HARDWARE NFC] {uid}")
                        controller.emit("nfc_tapped", uid)
                    if hardware.button.poll():
                        controller.emit("button_pressed")
                    hardware.display.tick()
                except httpx.HTTPError as exc:
                    show_error(exc)
                    controller.offline()
                    time.sleep(2)
        else:
            print("Commands: tap DEMO-001 | tap UNKNOWN | press | status | retry | replay | reset | quit")
            while True:
                command = input("mock> ").strip()
                try:
                    if command == "quit":
                        break
                    if command.startswith("tap "):
                        hardware.leds.show("blue")
                        controller.emit("nfc_tapped", command[4:].strip().upper())
                    elif command == "press":
                        hardware.leds.show("blue")
                        controller.emit("button_pressed")
                    elif command == "status":
                        controller.sync()
                        print(json.dumps(api.status(), indent=2))
                    elif command == "retry":
                        controller.retry()
                    elif command == "replay" and controller.last_event:
                        print(api.event(controller.last_event))
                        controller.sync()
                    elif command == "reset":
                        controller.emit("session_reset")
                    else:
                        print("Use tap DEMO-001, tap UNKNOWN, press, status, retry, replay, reset or quit")
                except (httpx.HTTPError, ValueError, OSError) as exc:
                    show_error(exc)
                    controller.offline()
                    print("No new request is assumed accepted. Use retry to resolve the SAME event ID.")
    except (KeyboardInterrupt, EOFError):
        print("\nStopped.")
    finally:
        hardware.close()
        api.close()


if __name__ == "__main__":
    main()
