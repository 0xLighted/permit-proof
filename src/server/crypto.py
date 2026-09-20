"""
PermitProof - Stage 2 Cryptographic & Identity Engine
Implements key derivation, identifier hashing, and message HMAC verification
as specified in STAGE2_HANDOFF.md.
"""

import hmac
import hashlib
import base64
import os
from typing import Tuple

HEX_CHARS = frozenset("0123456789abcdef")

def _load_dotenv_if_needed():
    if "MASTER_SECRET" not in os.environ and os.path.exists(".env"):
        try:
            with open(".env", "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        os.environ.setdefault(k.strip(), v.strip().strip("'\""))
        except Exception:
            pass


def get_master_secret() -> bytes:
    """
    Retrieves the raw master secret bytes from environment variable MASTER_SECRET.
    Supports base64 (standard) or 64-character hex encoding.
    """
    _load_dotenv_if_needed()
    val = os.environ.get("MASTER_SECRET")
    if not val:
        raise ValueError("MASTER_SECRET environment variable is not set (check .env or environment).")

    val = val.strip()
    # Support 64-character hex string if provided in .env
    if len(val) == 64 and all(c in HEX_CHARS for c in val.lower()):
        return bytes.fromhex(val)

    try:
        raw_bytes = base64.b64decode(val)
        if len(raw_bytes) < 32:
            raise ValueError(f"Master secret must be at least 32 bytes, got {len(raw_bytes)}")
        return raw_bytes
    except Exception as e:
        raise ValueError(f"Invalid MASTER_SECRET (expected base64 or 64-hex): {e}")


def derive_keys(master: bytes) -> Tuple[bytes, bytes, bytes]:
    """
    Derives purpose-specific keys using HMAC-SHA256 with domain labels:
    - K_device = HMAC-SHA256(master, UTF8("iot-zt:v1:device-token"))
    - K_card   = HMAC-SHA256(master, UTF8("iot-zt:v1:card-token"))
    - K_msg    = HMAC-SHA256(master, UTF8("iot-zt:v1:access-message"))
    """
    k_device = hmac.new(master, b"iot-zt:v1:device-token", hashlib.sha256).digest()
    k_card = hmac.new(master, b"iot-zt:v1:card-token", hashlib.sha256).digest()
    k_msg = hmac.new(master, b"iot-zt:v1:access-message", hashlib.sha256).digest()
    return k_device, k_card, k_msg


def derive_result_key(master: bytes) -> bytes:
    """
    Derives key for authenticating access decision grants sent to the device:
    - K_res = HMAC-SHA256(master, UTF8("iot-zt:v1:result-grant"))
    """
    return hmac.new(master, b"iot-zt:v1:result-grant", hashlib.sha256).digest()


def compute_device_id_hash(k_device: bytes, canonical_pi_id: str) -> str:
    """
    device_id_hash = lowercase_hex(HMAC-SHA256(K_device, UTF8(canonical_Pi_ID)))
    """
    return hmac.new(k_device, canonical_pi_id.encode("utf-8"), hashlib.sha256).hexdigest().lower()


def compute_card_id_hash(k_card: bytes, raw_uid_bytes: bytes) -> str:
    """
    card_id_hash = lowercase_hex(HMAC-SHA256(K_card, raw_UID_bytes))
    """
    return hmac.new(k_card, raw_uid_bytes, hashlib.sha256).hexdigest().lower()


def build_signing_bytes(device_id_hash: str, card_id_hash: str, nonce: str) -> bytes:
    """
    signing_bytes = UTF8(
      "access-v1\n" +
      device_id_hash + "\n" +
      card_id_hash + "\n" +
      nonce
    )
    """
    return f"access-v1\n{device_id_hash}\n{card_id_hash}\n{nonce}".encode("utf-8")


def compute_message_hmac(k_msg: bytes, device_id_hash: str, card_id_hash: str, nonce: str) -> str:
    """
    message_hmac = lowercase_hex(HMAC-SHA256(K_msg, signing_bytes))
    """
    signing_bytes = build_signing_bytes(device_id_hash, card_id_hash, nonce)
    return hmac.new(k_msg, signing_bytes, hashlib.sha256).hexdigest().lower()


def verify_message_hmac(k_msg: bytes, device_id_hash: str, card_id_hash: str, nonce: str, expected_hmac: str) -> bool:
    """
    Recomputes the HMAC and performs constant-time comparison.
    """
    if not is_valid_hex64(expected_hmac):
        return False
    computed = compute_message_hmac(k_msg, device_id_hash, card_id_hash, nonce)
    return hmac.compare_digest(computed, expected_hmac.lower())


def is_valid_hex64(val: str) -> bool:
    """Validates that string is exactly 64 lowercase hexadecimal characters."""
    return isinstance(val, str) and len(val) == 64 and all(c in HEX_CHARS for c in val)


def hash_token(token: str) -> str:
    """Hashes opaque tokens (result tokens, email approval tokens) before storing."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def build_grant_signing_bytes(attempt_id: str, device_id_hash: str, decision: str, expires_at: int) -> bytes:
    """
    grant_signing_bytes = UTF8(
      "grant-v1\n" +
      attempt_id + "\n" +
      device_id_hash + "\n" +
      decision + "\n" +
      str(expires_at)
    )
    """
    return f"grant-v1\n{attempt_id}\n{device_id_hash}\n{decision}\n{expires_at}".encode("utf-8")


def compute_grant_signature(k_res: bytes, attempt_id: str, device_id_hash: str, decision: str, expires_at: int) -> str:
    """
    grant_signature = lowercase_hex(HMAC-SHA256(K_res, grant_signing_bytes))
    """
    signing_bytes = build_grant_signing_bytes(attempt_id, device_id_hash, decision, expires_at)
    return hmac.new(k_res, signing_bytes, hashlib.sha256).hexdigest().lower()


def verify_grant_signature(
    k_res: bytes,
    attempt_id: str,
    device_id_hash: str,
    decision: str,
    expires_at: int,
    signature: str,
    current_time: float = None
) -> Tuple[bool, str]:
    """
    Verifies grant authenticity, ensures it is for this device, and checks that it has not expired.
    Returns (is_valid, reason).
    """
    if not is_valid_hex64(signature):
        return False, "INVALID_SIGNATURE_FORMAT"

    expected = compute_grant_signature(k_res, attempt_id, device_id_hash, decision, expires_at)
    if not hmac.compare_digest(expected, signature.lower()):
        return False, "SIGNATURE_MISMATCH"

    now = current_time if current_time is not None else __import__("time").time()
    if now > expires_at:
        return False, "GRANT_EXPIRED"

    return True, "VALID"
