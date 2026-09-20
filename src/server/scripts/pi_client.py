"""
PermitProof - Stage 2 Raspberry Pi NFC Client & LED State Machine
Executes the zero-trust card-tap protocol against the FastAPI server as specified in STAGE2_HANDOFF.md.
Supports both physical PN532 / GPIO LEDs and interactive simulated hardware mode.
"""

import sys
import os
import time
import argparse
import urllib.request
import urllib.parse
import json

from server.crypto import (
    get_master_secret,
    derive_keys,
    derive_result_key,
    compute_device_id_hash,
    compute_card_id_hash,
    compute_message_hmac,
    verify_grant_signature
)

# Optional hardware GPIO support for Raspberry Pi
try:
    import RPi.GPIO as GPIO
    HAS_GPIO = True
except ImportError:
    HAS_GPIO = False

# ANSI color codes for simulated LED indicators
COLOR_RED = "\033[91m"
COLOR_YELLOW = "\033[93m"
COLOR_GREEN = "\033[92m"
COLOR_RESET = "\033[0m"


class PiClient:
    def __init__(self, server_url: str, device_id: str, red_pin: int = 17, yellow_pin: int = 27, green_pin: int = 22):
        self.server_url = server_url.rstrip("/")
        self.device_id = device_id
        self.red_pin = red_pin
        self.yellow_pin = yellow_pin
        self.green_pin = green_pin

        master = get_master_secret()
        self.k_dev, self.k_card, self.k_msg = derive_keys(master)
        self.k_res = derive_result_key(master)
        self.device_id_hash = compute_device_id_hash(self.k_dev, self.device_id)

        # Track consumed attempt IDs to enforce strict single-use / anti-replay on the hardware
        self.consumed_grant_attempts = set()

        self._init_gpio()
        self.set_led_state("IDLE_CLOSED")

    def _init_gpio(self):
        if HAS_GPIO:
            try:
                GPIO.setmode(GPIO.BCM)
                GPIO.setwarnings(False)
                for pin in (self.red_pin, self.yellow_pin, self.green_pin):
                    GPIO.setup(pin, GPIO.OUT)
                    GPIO.output(pin, GPIO.LOW)
            except Exception as e:
                print(f"[!] GPIO init warning: {e}")

    def set_led_state(self, state: str):
        """
        Updates the physical LEDs or terminal indicators according to STAGE2_HANDOFF.md:
        - IDLE_CLOSED: Red steady
        - CHALLENGE_PENDING: Yellow blinking
        - VERIFYING: Yellow blinking
        - AWAITING_EMAIL: Yellow blinking
        - APPROVED: Green blinking
        - DENIED: Red blinking, then Red steady
        """
        if state == "IDLE_CLOSED":
            if HAS_GPIO:
                GPIO.output(self.red_pin, GPIO.HIGH)
                GPIO.output(self.yellow_pin, GPIO.LOW)
                GPIO.output(self.green_pin, GPIO.LOW)
            print(f"{COLOR_RED}[● LED: RED STEADY]{COLOR_RESET} Reader is IDLE / CLOSED. Waiting for card tap...")

        elif state in ("CHALLENGE_PENDING", "VERIFYING", "AWAITING_EMAIL"):
            if HAS_GPIO:
                GPIO.output(self.red_pin, GPIO.LOW)
                GPIO.output(self.yellow_pin, GPIO.HIGH)
                GPIO.output(self.green_pin, GPIO.LOW)
            print(f"{COLOR_YELLOW}[◐ LED: YELLOW BLINKING]{COLOR_RESET} State: {state} — Verification / email approval in progress...")

        elif state == "APPROVED":
            if HAS_GPIO:
                GPIO.output(self.red_pin, GPIO.LOW)
                GPIO.output(self.yellow_pin, GPIO.LOW)
                GPIO.output(self.green_pin, GPIO.HIGH)
            print(f"{COLOR_GREEN}[● LED: GREEN BLINKING]{COLOR_RESET} State: APPROVED — Access granted! Room unlocked.")

        elif state == "DENIED":
            if HAS_GPIO:
                GPIO.output(self.green_pin, GPIO.LOW)
                GPIO.output(self.yellow_pin, GPIO.LOW)
                for _ in range(3):
                    GPIO.output(self.red_pin, GPIO.HIGH)
                    time.sleep(0.3)
                    GPIO.output(self.red_pin, GPIO.LOW)
                    time.sleep(0.3)
                GPIO.output(self.red_pin, GPIO.HIGH)
            print(f"{COLOR_RED}[✖ LED: RED BLINKING -> RED STEADY]{COLOR_RESET} State: DENIED — Access rejected. Failing closed.")

    def tap_card(self, raw_uid_bytes: bytes) -> bool:
        """
        Executes the full 3-step zero-trust cryptographic protocol:
        1. GET /api/v1/challenge
        2. POST /api/v1/access-attempts
        3. GET /api/v1/access-attempts/{id}/result (held GET)
        """
        card_id_hash = compute_card_id_hash(self.k_card, raw_uid_bytes)
        print("\n" + "=" * 75)
        print("  PERMITPROOF PI ACCESS SEQUENCE INITIATED")
        print("=" * 75)
        print(f"Device ID          : {self.device_id}")
        print(f"Device Hash (K_dev): {self.device_id_hash[:16]}...{self.device_id_hash[-8:]}")
        print(f"Raw Card UID       : {raw_uid_bytes.hex()}")
        print(f"Card Hash (K_card) : {card_id_hash[:16]}...{card_id_hash[-8:]}")
        print(f"API Target Host    : {self.server_url}")

        # ----------------------------------------------------------------------
        # Step 1: Request Challenge Nonce (30s window)
        # ----------------------------------------------------------------------
        self.set_led_state("CHALLENGE_PENDING")
        challenge_url = f"{self.server_url}/api/v1/challenge?device_id_hash={self.device_id_hash}"
        try:
            req = urllib.request.Request(challenge_url, headers={"User-Agent": "PermitProof-Pi/2.0"})
            with urllib.request.urlopen(req, timeout=10) as resp:
                challenge_data = json.loads(resp.read().decode())
                nonce = challenge_data["nonce"]
                expires_in = challenge_data["expires_in_seconds"]
                print(f"[1/3] Challenge Nonce Acquired: {nonce} (Expires in {expires_in}s)")
        except Exception as e:
            print(f"[-] Failed to acquire challenge: {e}")
            self.set_led_state("DENIED")
            return False

        # ----------------------------------------------------------------------
        # Step 2: Compute HMAC and Submit Access Attempt
        # ----------------------------------------------------------------------
        self.set_led_state("VERIFYING")
        hmac_sig = compute_message_hmac(self.k_msg, self.device_id_hash, card_id_hash, nonce)
        payload = {
            "device_id_hash": self.device_id_hash,
            "card_id_hash": card_id_hash,
            "nonce": nonce,
            "message_hmac": hmac_sig
        }

        attempt_url = f"{self.server_url}/api/v1/access-attempts"
        try:
            data_bytes = json.dumps(payload).encode("utf-8")
            post_req = urllib.request.Request(
                attempt_url,
                data=data_bytes,
                headers={"Content-Type": "application/json", "User-Agent": "PermitProof-Pi/2.0"}
            )
            with urllib.request.urlopen(post_req, timeout=15) as resp:
                attempt_res = json.loads(resp.read().decode())
                attempt_id = attempt_res["attempt_id"]
                result_token = attempt_res["result_token"]
                email_deadline = attempt_res.get("expires_in_seconds", 120)
                print(f"[2/3] Access Attempt Accepted (202): ID={attempt_id}")
                print(f"      Status: PENDING_EMAIL_APPROVAL (Deadline: {email_deadline}s)")
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            print(f"[-] Attempt Rejected (HTTP {e.code}): {err_body}")
            self.set_led_state("DENIED")
            return False
        except Exception as e:
            print(f"[-] Connection Error: {e}")
            self.set_led_state("DENIED")
            return False

        # ----------------------------------------------------------------------
        # Step 3: Held Result GET (Waits for Email Approval)
        # ----------------------------------------------------------------------
        self.set_led_state("AWAITING_EMAIL")
        print("[3/3] Holding connection awaiting technician email magic-link approval...")
        result_url = f"{self.server_url}/api/v1/access-attempts/{attempt_id}/result"
        try:
            get_res_req = urllib.request.Request(
                result_url,
                headers={
                    "Authorization": f"Bearer {result_token}",
                    "User-Agent": "PermitProof-Pi/2.0"
                }
            )
            # Timeout must comfortably exceed the 120s email window
            with urllib.request.urlopen(get_res_req, timeout=130) as resp:
                final_res = json.loads(resp.read().decode())
                status = final_res.get("status")
                decision = final_res.get("decision")

                if status == "APPROVED" and decision == "ACCESS_GRANTED":
                    res_attempt_id = final_res.get("attempt_id", attempt_id)
                    grant_expires_at = final_res.get("grant_expires_at")
                    grant_sig = final_res.get("grant_signature")

                    # Security Verification 1: Replay protection - Ensure this attempt has not already been used
                    if res_attempt_id in self.consumed_grant_attempts:
                        print(f"\n[-] SECURITY VIOLATION: Access grant for attempt {res_attempt_id} has already been consumed! Rejecting replayed grant.")
                        self.set_led_state("DENIED")
                        return False

                    # Security Verification 2: Cryptographic Signature & Expiration verification
                    if not grant_sig or grant_expires_at is None:
                        print("\n[-] SECURITY VIOLATION: Missing cryptographic grant signature or expiry on success response. Rejecting forged message.")
                        self.set_led_state("DENIED")
                        return False

                    valid, reason = verify_grant_signature(
                        k_res=self.k_res,
                        attempt_id=res_attempt_id,
                        device_id_hash=self.device_id_hash,
                        decision=decision,
                        expires_at=grant_expires_at,
                        signature=grant_sig
                    )

                    if not valid:
                        if reason == "GRANT_EXPIRED":
                            print(f"\n[-] SECURITY VIOLATION: Access grant has expired ({grant_expires_at} < current time). Rejecting stale approval.")
                        else:
                            print(f"\n[-] SECURITY VIOLATION: Cryptographic grant signature verification failed ({reason}). Rejecting tampered/replayed grant.")
                        self.set_led_state("DENIED")
                        return False

                    # Mark attempt as consumed so this grant can never be replayed to this reader
                    self.consumed_grant_attempts.add(res_attempt_id)

                    print(f"\n[+] Final Result: APPROVED! Decision: {decision}")
                    print(f"    HMAC Grant Verified: VALID (Expires: {grant_expires_at})")
                    self.set_led_state("APPROVED")
                    # Hold green indication for 5 seconds, then return to idle closed
                    time.sleep(5)
                    self.set_led_state("IDLE_CLOSED")
                    return True
                else:
                    print(f"\n[-] Final Result: {status}. Decision: {decision}")
                    self.set_led_state("DENIED")
                    return False
        except Exception as e:
            print(f"[-] Result query failed or timed out: {e}")
            self.set_led_state("DENIED")
            return False


def main():
    parser = argparse.ArgumentParser(description="PermitProof Raspberry Pi Access Client")
    parser.add_argument("--server", default="http://localhost:8000", help="PermitProof API URL (default: http://localhost:8000)")
    parser.add_argument("--device-id", default="pi-server-room-001", help="Canonical Pi ID (default: pi-server-room-001)")
    parser.add_argument("--uid-hex", default="04a2b3c4d5e6f7", help="Simulated raw MIFARE UID hex (default: 04a2b3c4d5e6f7)")
    parser.add_argument("--interactive", action="store_true", help="Run interactive tap prompt loop")
    args = parser.parse_args()

    client = PiClient(server_url=args.server, device_id=args.device_id)

    if args.interactive:
        print("\n--- PermitProof Interactive Pi Station Ready ---")
        print("Press Enter to tap default card, type a hex UID, or 'q' to quit.")
        while True:
            try:
                user_input = input("\n[CARD-TAP PROMPT] Enter card UID hex (default: " + args.uid_hex + ") > ").strip()
                if user_input.lower() == "q":
                    break
                uid_hex = user_input if user_input else args.uid_hex
                raw_uid = bytes.fromhex(uid_hex.replace(":", "").replace(" ", ""))
                client.tap_card(raw_uid)
            except KeyboardInterrupt:
                break
            except Exception as e:
                print(f"[!] Error: {e}")
    else:
        raw_uid = bytes.fromhex(args.uid_hex.replace(":", "").replace(" ", ""))
        client.tap_card(raw_uid)


if __name__ == "__main__":
    main()
