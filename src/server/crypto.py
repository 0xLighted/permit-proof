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

# Default 32-byte master secret for lab/test environments if not in env
DEFAULT_MASTER_SECRET_B64 = base64.b64encode(b"permitproof-master-secret-32bytes!").decode("ascii")


def get_master_secret() -> bytes:
    """
    Retrieves the raw master secret bytes from environment variable MASTER_SECRET.
    Falls back to a secure lab default if not set.
    """
    b64_val = os.environ.get("MASTER_SECRET", DEFAULT_MASTER_SECRET_B64)
    try:
        raw_bytes = base64.b64decode(b64_val)
        if len(raw_bytes) < 32:
            raise ValueError(f"Master secret must be at least 32 bytes, got {len(raw_bytes)}")
        return raw_bytes
    except Exception as e:
        raise ValueError(f"Invalid base64 MASTER_SECRET: {e}")


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
