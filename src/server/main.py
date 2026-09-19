"""
PermitProof - Stage 2: Card-Tap Trust & Server-Room Access API
Implements challenge-response, HMAC verification, pre-approval job checks,
held result polling, and email magic-link approval per STAGE2_HANDOFF.md.
"""

from fastapi import FastAPI, HTTPException, Header, Query, status
from fastapi.responses import HTMLResponse
import secrets
import time
import uuid
import asyncio
from typing import Optional

from server.crypto import (
    get_master_secret,
    derive_keys,
    verify_message_hmac,
    hash_token,
    is_valid_hex64
)
from server.schemas import (
    ChallengeResponse,
    AccessAttemptRequest,
    AccessAttemptResponse,
    AttemptResultResponse
)
from server.store import store

app = FastAPI(
    title="PermitProof Stage 2 Access API",
    description="Zero-trust card-tap authentication and pre-approved server-room access",
    version="2.0.0"
)


@app.get("/", tags=["Health"])
@app.get("/health", tags=["Health"])
async def health():
    return {
        "status": "ONLINE",
        "service": "PermitProof Access API",
        "stage": "Stage 2 - Card-Tap Trust & Zero-Trust Pre-Approval",
        "timestamp": time.time()
    }


# ==============================================================================
# 1. Challenge Endpoint: GET /api/v1/challenge?device_id_hash=<64-hex>
# ==============================================================================
@app.get("/api/v1/challenge", response_model=ChallengeResponse, tags=["Access Protocol"])
async def get_challenge(device_id_hash: str = Query(..., description="64-hex keyed device hash")):
    """
    Issues an unpredictable, single-use, 30-second challenge nonce bound to the registered Pi device.
    """
    # 1. Validate format
    if not is_valid_hex64(device_id_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid device_id_hash format. Must be exactly 64 lowercase hex characters."
        )

    # 2. Lookup registered device (do not leak details)
    device = store.get_device(device_id_hash)
    if not device:
        store.log_audit_event(
            event_type="CHALLENGE_REQUEST_REJECTED",
            outcome="UNKNOWN_DEVICE",
            device_hash=device_id_hash
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Device not recognized or inactive."
        )

    # 3. Generate single-use nonce & register
    nonce = secrets.token_urlsafe(24)
    store.save_challenge(nonce=nonce, device_id_hash=device_id_hash, lifetime_seconds=30)

    store.log_audit_event(
        event_type="CHALLENGE_ISSUED",
        outcome="SUCCESS",
        device_hash=device_id_hash,
        metadata={"nonce": nonce, "expires_in_seconds": 30}
    )

    return ChallengeResponse(nonce=nonce, expires_in_seconds=30)


# ==============================================================================
# 2. Access Attempts Endpoint: POST /api/v1/access-attempts
# ==============================================================================
@app.post(
    "/api/v1/access-attempts",
    response_model=AccessAttemptResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["Access Protocol"]
)
async def submit_access_attempt(req: AccessAttemptRequest):
    """
    Processes a signed access attempt from the Pi.
    Verifies HMAC, single-use nonce, registered card, and accepted job pre-approval.
    """
    # Step 1: Find registered, enabled device
    device = store.get_device(req.device_id_hash)
    if not device:
        store.log_audit_event("ACCESS_ATTEMPT_DENIED", "UNKNOWN_DEVICE", device_hash=req.device_id_hash)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Device is not authorized or is disabled."
        )

    # Step 2: Recompute and constant-time check HMAC using K_msg
    try:
        master = get_master_secret()
        _, _, k_msg = derive_keys(master)
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Crypto error: {e}")

    hmac_ok = verify_message_hmac(
        k_msg=k_msg,
        device_id_hash=req.device_id_hash,
        card_id_hash=req.card_id_hash,
        nonce=req.nonce,
        expected_hmac=req.message_hmac
    )
    if not hmac_ok:
        store.log_audit_event(
            "ACCESS_ATTEMPT_DENIED",
            "INVALID_HMAC",
            device_hash=req.device_id_hash,
            card_hash=req.card_id_hash
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Message HMAC verification failed. Signal is not genuine."
        )

    # Step 3: Atomically consume the nonce
    consumed, reason = store.consume_nonce(req.nonce, req.device_id_hash)
    if not consumed:
        store.log_audit_event(
            "ACCESS_ATTEMPT_DENIED",
            f"NONCE_CHECK_FAILED_{reason}",
            device_hash=req.device_id_hash,
            card_hash=req.card_id_hash
        )
        if reason == "NONCE_EXPIRED":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Challenge nonce has expired (30s window exceeded).")
        if reason == "NONCE_DEVICE_MISMATCH":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Nonce was not issued for this device.")
        # Replay attempt or unknown nonce
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Challenge nonce has already been consumed or is invalid.")

    # Step 4: Find registered card owner
    user = store.get_user(req.card_id_hash)
    if not user:
        store.log_audit_event(
            "ACCESS_ATTEMPT_DENIED",
            "UNREGISTERED_CARD",
            device_hash=req.device_id_hash,
            card_hash=req.card_id_hash
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Card UID is not registered to an active user."
        )

    # Step 5: Find an accepted, incomplete job for this technician and this device/room
    job = store.find_accepted_job(card_id_hash=req.card_id_hash, device_id_hash=req.device_id_hash)
    if not job:
        store.log_audit_event(
            "ACCESS_ATTEMPT_DENIED",
            "NO_ACCEPTED_JOB",
            device_hash=req.device_id_hash,
            card_hash=req.card_id_hash,
            metadata={"room_id": device.get("room_id")}
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access pre-approval failed: No accepted, incomplete job exists for this technician in this room."
        )

    # Step 6: Create pending attempt with 120s email deadline
    attempt_id = str(uuid.uuid4())
    result_token = secrets.token_urlsafe(32)
    result_token_hash = hash_token(result_token)
    email_token = secrets.token_urlsafe(32)
    email_token_hash = hash_token(email_token)

    store.create_attempt(
        attempt_id=attempt_id,
        device_id_hash=req.device_id_hash,
        card_id_hash=req.card_id_hash,
        job_id=job["job_id"],
        result_token_hash=result_token_hash,
        lifetime_seconds=120
    )
    store.save_approval_token(
        raw_token=email_token,
        token_hash=email_token_hash,
        attempt_id=attempt_id,
        expires_in_seconds=120
    )

    # Step 7: Log audit and simulate email dispatch to registered user
    approval_url = f"/api/v1/approve?token={email_token}"
    store.log_audit_event(
        "ACCESS_ATTEMPT_PENDING_EMAIL",
        "PENDING",
        attempt_id=attempt_id,
        device_hash=req.device_id_hash,
        card_hash=req.card_id_hash,
        metadata={
            "job_id": job["job_id"],
            "recipient_email": user.get("email"),
            "approval_url": approval_url
        }
    )

    print("\n" + "=" * 70)
    print(f"[STAGE 2 EMAIL DISPATCH SIMULATED]")
    print(f"  To: {user.get('full_name')} <{user.get('email')}>")
    print(f"  Attempt ID: {attempt_id}")
    print(f"  One-Time Magic Approval Link: {approval_url}")
    print("=" * 70 + "\n")

    return AccessAttemptResponse(
        attempt_id=attempt_id,
        status="PENDING_EMAIL_APPROVAL",
        result_token=result_token,
        expires_in_seconds=120
    )


# ==============================================================================
# 3. Held Result Endpoint: GET /api/v1/access-attempts/{attempt_id}/result
# ==============================================================================
@app.get(
    "/api/v1/access-attempts/{attempt_id}/result",
    response_model=AttemptResultResponse,
    tags=["Access Protocol"]
)
async def get_attempt_result(
    attempt_id: str,
    authorization: Optional[str] = Header(None),
    timeout: float = Query(120.0, description="Max hold wait time in seconds (up to remaining deadline)")
):
    """
    Held GET called by the Pi. Awaits email magic-link approval up to the 120-second deadline.
    Requires Bearer <result_token> header.
    """
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header. Expected Bearer <result_token>."
        )
    result_token = authorization.split("Bearer ", 1)[1].strip()
    result_token_hash = hash_token(result_token)

    attempt = store.get_attempt(attempt_id)
    if not attempt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attempt not found.")

    if attempt["result_token_hash"] != result_token_hash:
        store.log_audit_event("RESULT_POLL_UNAUTHORIZED", "INVALID_TOKEN", attempt_id=attempt_id)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid result token for this attempt.")

    # Check if already decided
    if attempt["status"] != "PENDING_EMAIL_APPROVAL":
        return AttemptResultResponse(
            attempt_id=attempt_id,
            status=attempt["status"],
            decision=attempt.get("decision") or "ACCESS_DENIED"
        )

    # Calculate remaining time up to 120s limit
    now = time.time()
    remaining = attempt["expires_at"] - now
    wait_time = max(0.0, min(timeout, remaining))

    if wait_time <= 0:
        store.reject_attempt(attempt_id, reason="EMAIL_DEADLINE_EXPIRED")
        return AttemptResultResponse(
            attempt_id=attempt_id,
            status="EXPIRED",
            decision="ACCESS_DENIED"
        )

    # Asynchronously wait for email approval event without locking SQLite or workers
    event = store.get_attempt_event(attempt_id)
    try:
        await asyncio.wait_for(event.wait(), timeout=wait_time)
    except asyncio.TimeoutError:
        # Re-check attempt in case it was resolved right on the boundary
        attempt = store.get_attempt(attempt_id)
        if attempt["status"] == "PENDING_EMAIL_APPROVAL":
            store.reject_attempt(attempt_id, reason="EMAIL_DEADLINE_EXPIRED")
            return AttemptResultResponse(
                attempt_id=attempt_id,
                status="EXPIRED",
                decision="ACCESS_DENIED"
            )

    attempt = store.get_attempt(attempt_id)
    return AttemptResultResponse(
        attempt_id=attempt_id,
        status=attempt["status"],
        decision=attempt.get("decision") or "ACCESS_DENIED"
    )


# ==============================================================================
# 4. Email Approval Endpoint: GET /api/v1/approve?token=<opaque-email-token>
# ==============================================================================
@app.get("/api/v1/approve", tags=["Email Approval"])
async def approve_via_magic_link(token: str = Query(..., description="One-time opaque email approval token")):
    """
    Called by technician clicking the emailed magic link in a browser.
    Atomically transitions the pending attempt to APPROVED and unblocks the Pi's held GET.
    """
    success, attempt_id, reason = store.consume_approval_token(token)
    if not success:
        store.log_audit_event("EMAIL_APPROVAL_FAILED", reason, attempt_id=attempt_id)
        html_fail = f"""
        <!DOCTYPE html>
        <html>
        <head><title>Access Approval Failed</title></head>
        <body style="font-family: sans-serif; text-align: center; padding: 50px; background: #0f172a; color: #f87171;">
            <h2>Access Approval Failed</h2>
            <p>Reason: <b>{reason}</b></p>
            <p style="color: #94a3b8;">This magic link is invalid, expired, or has already been used.</p>
        </body>
        </html>
        """
        return HTMLResponse(content=html_fail, status_code=status.HTTP_400_BAD_REQUEST)

    store.log_audit_event("EMAIL_APPROVAL_SUCCESS", "APPROVED", attempt_id=attempt_id)
    html_success = f"""
    <!DOCTYPE html>
    <html>
    <head><title>Access Approved</title></head>
    <body style="font-family: sans-serif; text-align: center; padding: 50px; background: #0f172a; color: #4ade80;">
        <h2>Access Approved!</h2>
        <p>Attempt ID: <code>{attempt_id}</code></p>
        <p style="color: #94a3b8;">Server room reader has been authorized. The door indicator is blinking green.</p>
    </body>
    </html>
    """
    return HTMLResponse(content=html_success, status_code=status.HTTP_200_OK)


def main():
    import uvicorn
    print("\n" + "=" * 80)
    print("  PERMITPROOF: STAGE 2 ACCESS CONTROL SERVER")
    print("  Listening on: http://0.0.0.0:8080")
    print("  API Docs    : http://0.0.0.0:8080/docs")
    print("=" * 80 + "\n")
    uvicorn.run(app, host="0.0.0.0", port=8080)


if __name__ == "__main__":
    main()
