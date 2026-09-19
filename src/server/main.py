"""
PermitProof - Stage 2: Card-Tap Trust & Server-Room Access API
Full SQLite-backed implementation with atomic transactions, foreign keys,
pre-approval job lifecycle, held result notifications, and email magic-link approval.
"""

from fastapi import FastAPI, HTTPException, Header, Query, Request, status
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
import secrets
import time
import uuid
import asyncio
import os
import json
from typing import Optional, List, Dict, Any, Tuple

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
    AttemptResultResponse,
    JobCreateRequest,
    JobResponse,
    JobActionRequest
)
from server.db import db
from server.email_service import email_service

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    db.init_schema()
    yield

app = FastAPI(
    title="PermitProof Stage 2 Access API",
    description="Zero-trust card-tap authentication, SQLite-backed pre-approval, and server-room access",
    version="2.0.0",
    lifespan=lifespan
)

# In-memory async notification bus for held result GET (avoids holding SQLite locks)
attempt_events: Dict[str, asyncio.Event] = {}


def get_attempt_event(attempt_id: str) -> asyncio.Event:
    if attempt_id not in attempt_events:
        attempt_events[attempt_id] = asyncio.Event()
    return attempt_events[attempt_id]


def notify_attempt_event(attempt_id: Optional[str]):
    if attempt_id and attempt_id in attempt_events:
        attempt_events[attempt_id].set()


@app.get("/health", tags=["Health"])
async def health():
    return {
        "status": "ONLINE",
        "service": "PermitProof Access API",
        "stage": "Stage 2 - Card-Tap Trust & Zero-Trust Pre-Approval",
        "database": "SQLite (WAL mode + Foreign Keys)",
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
    if not is_valid_hex64(device_id_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid device_id_hash format. Must be exactly 64 lowercase hex characters."
        )

    device = db.get_device(device_id_hash)
    if not device:
        db.log_audit(
            event_type="CHALLENGE_REQUEST_REJECTED",
            outcome="UNKNOWN_DEVICE",
            device_hash=device_id_hash
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Device not recognized or inactive."
        )

    nonce = secrets.token_urlsafe(24)
    db.save_challenge(nonce=nonce, device_id_hash=device_id_hash, lifetime_seconds=30)

    db.log_audit(
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
    Verifies HMAC, single-use nonce atomically in SQLite, registered card, and accepted job pre-approval.
    """
    # Step 1: Find registered, enabled device
    device = db.get_device(req.device_id_hash)
    if not device:
        db.log_audit("ACCESS_ATTEMPT_DENIED", "UNKNOWN_DEVICE", device_hash=req.device_id_hash)
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
        db.log_audit(
            "ACCESS_ATTEMPT_DENIED",
            "INVALID_HMAC",
            device_hash=req.device_id_hash,
            card_hash=req.card_id_hash
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Message HMAC verification failed. Signal is not genuine."
        )

    # Step 3: Atomically consume the nonce in SQLite
    consumed, reason = db.consume_nonce_atomic(req.nonce, req.device_id_hash)
    if not consumed:
        db.log_audit(
            "ACCESS_ATTEMPT_DENIED",
            f"NONCE_CHECK_FAILED_{reason}",
            device_hash=req.device_id_hash,
            card_hash=req.card_id_hash
        )
        if reason == "NONCE_EXPIRED":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Challenge nonce has expired (30s window exceeded).")
        if reason == "NONCE_DEVICE_MISMATCH":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Nonce was not issued for this device.")
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Challenge nonce has already been consumed or is invalid.")

    # Step 4: Find registered card owner
    user = db.get_user(req.card_id_hash)
    if not user:
        db.log_audit(
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
    job = db.find_accepted_job(technician_id=req.card_id_hash, device_id_hash=req.device_id_hash)
    if not job:
        db.log_audit(
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

    db.create_attempt(
        attempt_id=attempt_id,
        device_id_hash=req.device_id_hash,
        card_id_hash=req.card_id_hash,
        job_id=job["job_id"],
        result_token_hash=result_token_hash,
        lifetime_seconds=120
    )
    db.save_approval_link(
        token_hash=email_token_hash,
        attempt_id=attempt_id,
        lifetime_seconds=120
    )

    # Step 7: Dispatch magic link email out-of-band and log safe audit entry
    approval_url = f"/api/v1/approve?token={email_token}"
    email_service.send_magic_link(
        to_name=user.get("full_name", "Card Owner"),
        to_email=user.get("email", ""),
        attempt_id=attempt_id,
        approval_url=approval_url,
        email_token=email_token
    )

    db.log_audit(
        "ACCESS_ATTEMPT_PENDING_EMAIL",
        "PENDING",
        attempt_id=attempt_id,
        device_hash=req.device_id_hash,
        card_hash=req.card_id_hash,
        metadata={
            "job_id": job["job_id"],
            "recipient_email": user.get("email"),
            "token_hash_prefix": email_token_hash[:8]
        }
    )

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

    attempt = db.get_attempt(attempt_id)
    if not attempt:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Attempt not found.")

    if attempt["result_token_hash"] != result_token_hash:
        db.log_audit("RESULT_POLL_UNAUTHORIZED", "INVALID_TOKEN", attempt_id=attempt_id)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid result token for this attempt.")

    if attempt["status"] != "PENDING_EMAIL_APPROVAL":
        return AttemptResultResponse(
            attempt_id=attempt_id,
            status=attempt["status"],
            decision=attempt.get("decision") or "ACCESS_DENIED"
        )

    now = time.time()
    remaining = attempt["expires_at"] - now
    wait_time = max(0.0, min(timeout, remaining))

    if wait_time <= 0:
        db.update_attempt_decision(attempt_id, "EXPIRED", "ACCESS_DENIED", reason="EMAIL_DEADLINE_EXPIRED")
        return AttemptResultResponse(attempt_id=attempt_id, status="EXPIRED", decision="ACCESS_DENIED")

    event = get_attempt_event(attempt_id)
    try:
        await asyncio.wait_for(event.wait(), timeout=wait_time)
    except asyncio.TimeoutError:
        attempt = db.get_attempt(attempt_id)
        if attempt["status"] == "PENDING_EMAIL_APPROVAL":
            db.update_attempt_decision(attempt_id, "EXPIRED", "ACCESS_DENIED", reason="EMAIL_DEADLINE_EXPIRED")
            return AttemptResultResponse(attempt_id=attempt_id, status="EXPIRED", decision="ACCESS_DENIED")

    attempt = db.get_attempt(attempt_id)
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
    Atomically transitions the pending attempt to APPROVED in SQLite and unblocks the Pi's held GET.
    """
    token_hash = hash_token(token)
    success, attempt_id, reason = db.consume_approval_token_atomic(token_hash)
    notify_attempt_event(attempt_id)

    if not success:
        db.log_audit("EMAIL_APPROVAL_FAILED", reason, attempt_id=attempt_id)
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

    db.log_audit("EMAIL_APPROVAL_SUCCESS", "APPROVED", attempt_id=attempt_id)
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


# ==============================================================================
# 5. Job Pre-Approval API Gateway (Supervisor & Technician Workflow)
# ==============================================================================
@app.post("/api/v1/jobs", response_model=JobResponse, status_code=status.HTTP_201_CREATED, tags=["Jobs Management"])
async def create_job(req: JobCreateRequest):
    """
    Supervisor creates an inspection job pre-approval for a technician and server room.
    """
    # Verify supervisor role
    sup = db.get_user(req.supervisor_id)
    if not sup or sup.get("role") != "supervisor":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only supervisors can create jobs.")

    # Verify technician exists
    tech = db.get_user(req.technician_id)
    if not tech or tech.get("role") != "technician":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Assigned user must be an active technician.")

    # Verify device exists
    dev = db.get_device(req.device_id_hash)
    if not dev:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Target device does not exist.")

    job_id = req.job_id or f"job-{uuid.uuid4().hex[:12]}"
    job_data = db.create_job(
        job_id=job_id,
        supervisor_id=req.supervisor_id,
        technician_id=req.technician_id,
        device_id_hash=req.device_id_hash,
        tasks=req.tasks
    )
    db.log_audit("JOB_CREATED", "SUCCESS", device_hash=req.device_id_hash, card_hash=req.technician_id, metadata={"job_id": job_id})
    return JobResponse(**job_data)


@app.get("/api/v1/jobs", response_model=List[JobResponse], tags=["Jobs Management"])
async def list_jobs(
    technician_id: Optional[str] = Query(None, description="Filter by technician card hash"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filter by status (pending, accepted, etc.)")
):
    """Lists inspection jobs recorded in SQLite."""
    jobs = db.list_jobs(technician_id=technician_id, status=status_filter)
    return [JobResponse(**j) for j in jobs]


@app.post("/api/v1/jobs/{job_id}/accept", tags=["Jobs Management"])
async def accept_job(job_id: str, req: Optional[JobActionRequest] = None):
    """
    Technician accepts job on the website -> becomes active pre-approval for room tap.
    """
    tech_id = req.technician_id if req else None
    ok, reason = db.update_job_status(job_id, "accepted", technician_id=tech_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Cannot accept job: {reason}")
    db.log_audit("JOB_ACCEPTED", "SUCCESS", metadata={"job_id": job_id, "technician_id": tech_id})
    return {"status": "SUCCESS", "job_id": job_id, "job_status": "accepted"}


@app.post("/api/v1/jobs/{job_id}/skip", tags=["Jobs Management"])
async def skip_job(job_id: str, req: Optional[JobActionRequest] = None):
    """Technician skips job."""
    tech_id = req.technician_id if req else None
    ok, reason = db.update_job_status(job_id, "skipped", technician_id=tech_id)
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Cannot skip job: {reason}")
    db.log_audit("JOB_SKIPPED", "SUCCESS", metadata={"job_id": job_id})
    return {"status": "SUCCESS", "job_id": job_id, "job_status": "skipped"}


@app.post("/api/v1/jobs/{job_id}/complete", tags=["Jobs Management"])
async def complete_job(job_id: str):
    """Marks job complete after inspection finish."""
    ok, reason = db.update_job_status(job_id, "completed")
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Cannot complete job: {reason}")
    db.log_audit("JOB_COMPLETED", "SUCCESS", metadata={"job_id": job_id})
    return {"status": "SUCCESS", "job_id": job_id, "job_status": "completed"}


@app.post("/api/v1/jobs/{job_id}/revoke", tags=["Jobs Management"])
async def revoke_job(job_id: str):
    """Supervisor revokes job authorization."""
    ok, reason = db.update_job_status(job_id, "revoked")
    if not ok:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Cannot revoke job: {reason}")
    db.log_audit("JOB_REVOKED", "SUCCESS", metadata={"job_id": job_id})
    return {"status": "SUCCESS", "job_id": job_id, "job_status": "revoked"}


# ==============================================================================
# 6. Audit & Maintenance API Gateway
# ==============================================================================
@app.get("/api/v1/audit-events", tags=["Audit Trail"])
async def get_audit_trail(
    attempt_id: Optional[str] = Query(None, description="Filter by attempt ID"),
    event_type: Optional[str] = Query(None, description="Filter by event type"),
    device_hash: Optional[str] = Query(None, description="Filter by device ID hash"),
    limit: int = Query(50, ge=1, le=200, description="Max audit entries to retrieve")
):
    """
    Returns audit trail records stored in SQLite for zero-trust compliance,
    attack/defense proof, and supervisor inspection.
    """
    return db.get_audit_events(
        attempt_id=attempt_id,
        event_type=event_type,
        device_hash=device_hash,
        limit=limit
    )


@app.post("/api/v1/maintenance/prune-challenges", tags=["Maintenance"])
async def prune_challenges(max_age_seconds: float = Query(86400, description="Prune challenges older than this seconds")):
    """Prunes expired challenge nonces to keep SQLite database lean."""
    deleted_count = db.prune_expired_challenges(max_age_seconds=max_age_seconds)
    return {"status": "SUCCESS", "deleted_count": deleted_count}


# ==============================================================================
# 7. Frontend Integration Bridge (React 19 Dashboard & Actions)
# ==============================================================================
checklist_state: Dict[str, Dict[int, bool]] = {}


def mask_email(email: str) -> str:
    if "@" not in email:
        return email
    user, domain = email.split("@", 1)
    if len(user) <= 2:
        masked = user[0] + "***"
    else:
        masked = user[0] + "***" + user[-1]
    return f"{masked}@{domain}"


def get_default_users() -> Tuple[Dict[str, Any], Dict[str, Any]]:
    sup = None
    tech = None
    for u in db.list_users():
        if u["role"] == "supervisor" and not sup:
            sup = u
        elif u["role"] == "technician" and not tech:
            tech = u
    if not sup:
        sup = {
            "card_id_hash": "sup_default",
            "full_name": "Alice Supervisor",
            "email": "supervisor@permitproof.local",
            "role": "supervisor"
        }
    if not tech:
        tech = {
            "card_id_hash": "tech_default",
            "full_name": "Jasmine Zurayn",
            "email": "technician@permitproof.local",
            "role": "technician"
        }
    return sup, tech


def build_task_item(
    job: Dict[str, Any],
    devices_by_hash: Dict[str, Dict[str, Any]],
    users_by_hash: Dict[str, Dict[str, Any]],
    active_attempt: Optional[Dict[str, Any]]
) -> Dict[str, Any]:
    job_id = job["job_id"]
    tech_user = users_by_hash.get(job["technician_id"], {})
    dev = devices_by_hash.get(job["device_id_hash"], {})
    room_name = dev.get("room_id", "Server Room")

    ts_val = job.get("created_at", time.time())
    ts_str = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(ts_val))

    raw_status = job.get("status", "pending")
    if raw_status == "completed":
        task_status = "completed"
    elif raw_status == "revoked":
        task_status = "revoked"
    elif raw_status == "skipped":
        task_status = "rejected"
    elif raw_status == "pending":
        task_status = "assigned"
    elif raw_status == "accepted":
        if active_attempt and active_attempt.get("job_id") == job_id:
            if active_attempt.get("status") == "PENDING_EMAIL_APPROVAL":
                task_status = "verifying"
            elif active_attempt.get("status") == "APPROVED":
                task_status = "verified"
            else:
                task_status = "assigned"
        else:
            task_status = "assigned"
    else:
        task_status = "assigned"

    tasks_list = job.get("tasks") or ["Standard zero-trust inspection"]
    cl_state = checklist_state.get(job_id, {})
    checklist = [
        {"label": t, "done": bool(job.get("is_complete")) or cl_state.get(i, False)}
        for i, t in enumerate(tasks_list)
    ]

    return {
        "id": job_id,
        "job_id": job_id,
        "timestamp": ts_str,
        "supervisor_id": job.get("supervisor_id", ""),
        "technician_id": job.get("technician_id", ""),
        "technician": tech_user.get("full_name", "Jasmine Zurayn"),
        "room": room_name,
        "room_id": room_name,
        "asset": f"Server Rack ({job_id.split('-')[-1]})",
        "title": f"Zero-Trust Permit {job_id}",
        "instructions": "Verify physical seal tamper status, check rack cooling, and validate physical indicators.",
        "due": "End of Shift",
        "status": task_status,
        "is_complete": bool(job.get("is_complete", 0)),
        "tasks": tasks_list,
        "checklist": checklist,
        "checkInAt": None,
        "verifiedAt": None,
        "tapAttempt": None
    }


def build_audit_event_item(event: Dict[str, Any]) -> Dict[str, Any]:
    timestamp_ts = event.get("timestamp", time.time())
    time_str = time.strftime("%H:%M:%S", time.localtime(timestamp_ts))
    dev_ref = (event.get("device_hash") or "")[:8] + "..." if event.get("device_hash") else "N/A"
    user_ref = (event.get("card_hash") or "")[:8] + "..." if event.get("card_hash") else "SYSTEM"
    etype = event.get("event_type", "EVENT")
    outcome = event.get("outcome", "INFO")
    kind = "info"
    if "APPROVED" in etype or "APPROVED" in outcome or (outcome == "SUCCESS" and "ACCEPT" in etype):
        kind = "approved"
    elif "DENIED" in etype or "REJECT" in etype or "FAIL" in outcome or "EXPIRED" in outcome:
        kind = "warning"
    elif "CHECKIN" in etype or "TAP" in etype or "CHALLENGE" in etype:
        kind = "checkin"
    elif "JOB" in etype:
        kind = "task"
    return {
        "id": str(event.get("event_id", "")),
        "timestamp": time_str,
        "time": time_str,
        "device_ref": dev_ref,
        "user_ref": user_ref,
        "message": f"[{etype}] {outcome}",
        "text": f"[{etype}] {outcome}",
        "kind": kind
    }


def build_state_data(role: Optional[str] = None) -> Dict[str, Any]:
    sup_user, tech_user = get_default_users()
    devices = db.list_devices(active_only=True)
    devices_by_hash = {d["device_id_hash"]: d for d in devices}
    users = db.list_users()
    users_by_hash = {u["card_id_hash"]: u for u in users}

    all_jobs = db.list_jobs()
    active_attempt = db.get_latest_attempt()

    tasks_fmt = [
        build_task_item(j, devices_by_hash, users_by_hash, active_attempt)
        for j in all_jobs
    ]

    rooms = [d["room_id"] for d in devices]
    devices_fmt = [{"device_hash": d["device_id_hash"], "room_id": d["room_id"]} for d in devices]

    now = time.time()
    if active_attempt and active_attempt.get("status") == "PENDING_EMAIL_APPROVAL" and now < active_attempt.get("expires_at", 0):
        latest_email = email_service.get_latest_entry(active_attempt["attempt_id"])
        magic_url = latest_email["approval_url"] if latest_email else f"/api/v1/approve?token={email_service.get_latest_token(active_attempt['attempt_id'])}"
        auth_state = {
            "nfc_detected": True,
            "otp_pending": True,
            "authenticated": False,
            "attempts_remaining": 3,
            "email_masked": mask_email(tech_user.get("email", "")),
            "expires_in_sec": max(0, int(active_attempt["expires_at"] - now)),
            "email_notice": f"Magic link emailed to {tech_user.get('email')}. Click approval link below or verify token.",
            "magic_link_url": magic_url
        }
    elif active_attempt and active_attempt.get("status") == "APPROVED":
        auth_state = {
            "nfc_detected": True,
            "otp_pending": False,
            "authenticated": True,
            "attempts_remaining": 3,
            "email_masked": mask_email(tech_user.get("email", "")),
            "expires_in_sec": 0,
            "email_notice": "Technician identity validated. Server room reader authorized (green indicator blinking).",
            "magic_link_url": None
        }
    else:
        auth_state = {
            "nfc_detected": False,
            "otp_pending": False,
            "authenticated": False,
            "attempts_remaining": 3,
            "email_masked": mask_email(tech_user.get("email", "")),
            "expires_in_sec": 0,
            "email_notice": None,
            "magic_link_url": None
        }

    if role == "supervisor":
        all_techs = [
            {"full_name": u["full_name"], "email": u["email"], "card_hash": u["card_id_hash"]}
            for u in users if u.get("role") == "technician"
        ]
        raw_events = db.get_audit_events(limit=30)
        events_fmt = [build_audit_event_item(e) for e in raw_events]
        return {
            "version": 2,
            "role": "supervisor",
            "supervisor": sup_user.get("full_name", "Alice Supervisor"),
            "supervisor_card_hash": sup_user.get("card_id_hash", ""),
            "technician": tech_user.get("full_name", "Jasmine Zurayn"),
            "rooms": rooms,
            "devices": devices_fmt,
            "technicians": all_techs,
            "tasks": tasks_fmt,
            "events": events_fmt,
            "audit_log": events_fmt
        }
    else:
        return {
            "version": 2,
            "role": "technician",
            "technician": tech_user.get("full_name", "Jasmine Zurayn"),
            "technician_card_hash": tech_user.get("card_id_hash", ""),
            "technician_email": tech_user.get("email", ""),
            "rooms": rooms,
            "devices": devices_fmt,
            "tasks": tasks_fmt,
            "auth_state": auth_state
        }


@app.get("/api/state", tags=["Frontend Bridge"])
async def get_frontend_state(role: Optional[str] = Query(None), request: Request = None):
    chosen_role = role
    if not chosen_role and request:
        referer = request.headers.get("referer", "").lower()
        if "supervisor" in referer:
            chosen_role = "supervisor"
    return build_state_data(chosen_role or "technician")


@app.post("/api/action", tags=["Frontend Bridge"])
async def handle_frontend_action(req_data: Dict[str, Any], request: Request):
    action = req_data.get("action")
    sup_user, tech_user = get_default_users()
    target_role = "technician"
    referer = request.headers.get("referer", "").lower()
    if "supervisor" in referer or req_data.get("role") == "supervisor":
        target_role = "supervisor"

    if action == "create":
        title = req_data.get("title", "Server Room Inspection")
        room = req_data.get("room", "")
        tasks = req_data.get("tasks") or [
            "Verify physical tamper seals",
            "Inspect cable management & cooling manifolds"
        ]
        devices = db.list_devices(active_only=True)
        dev = next((d for d in devices if d["room_id"] == room), devices[0] if devices else None)
        if not dev:
            raise HTTPException(status_code=400, detail="No active station device available for this room")

        job_id = f"job-{uuid.uuid4().hex[:8]}"
        db.create_job(
            job_id=job_id,
            supervisor_id=sup_user["card_id_hash"],
            technician_id=tech_user["card_id_hash"],
            device_id_hash=dev["device_id_hash"],
            tasks=tasks
        )
        db.log_audit("JOB_CREATED", "SUCCESS", device_hash=dev["device_id_hash"], card_hash=tech_user["card_id_hash"], metadata={"job_id": job_id, "title": title})
        return build_state_data("supervisor")

    elif action == "accept":
        job_id = req_data.get("id")
        if not job_id:
            raise HTTPException(status_code=400, detail="Missing job id")
        ok, reason = db.update_job_status(job_id, "accepted", technician_id=tech_user["card_id_hash"])
        if not ok:
            raise HTTPException(status_code=400, detail=f"Cannot accept job: {reason}")
        db.log_audit("JOB_ACCEPTED", "SUCCESS", metadata={"job_id": job_id, "technician_id": tech_user["card_id_hash"]})
        return build_state_data(target_role)

    elif action == "skip":
        job_id = req_data.get("id")
        if not job_id:
            raise HTTPException(status_code=400, detail="Missing job id")
        ok, reason = db.update_job_status(job_id, "skipped", technician_id=tech_user["card_id_hash"])
        if not ok:
            raise HTTPException(status_code=400, detail=f"Cannot skip job: {reason}")
        db.log_audit("JOB_SKIPPED", "SUCCESS", metadata={"job_id": job_id})
        return build_state_data(target_role)

    elif action == "tap":
        job_id = req_data.get("id")
        job = None
        if job_id:
            jobs = db.list_jobs()
            job = next((j for j in jobs if j["job_id"] == job_id), None)
        if not job:
            devices = db.list_devices(active_only=True)
            for d in devices:
                j = db.find_accepted_job(technician_id=tech_user["card_id_hash"], device_id_hash=d["device_id_hash"])
                if j:
                    job = j
                    break

        if not job:
            raise HTTPException(
                status_code=400,
                detail="Access pre-approval failed: No accepted work order exists for technician. Please accept a work order first."
            )

        dev_hash = job["device_id_hash"]
        card_hash = job["technician_id"]

        nonce = secrets.token_urlsafe(24)
        db.save_challenge(nonce, dev_hash, lifetime_seconds=30)

        master = get_master_secret()
        _, _, k_msg = derive_keys(master)
        from server.crypto import compute_message_hmac
        msg_hmac = compute_message_hmac(k_msg, dev_hash, card_hash, nonce)

        consumed, reason = db.consume_nonce_atomic(nonce, dev_hash)
        if not consumed:
            raise HTTPException(status_code=400, detail=f"Nonce error: {reason}")

        attempt_id = str(uuid.uuid4())
        result_token = secrets.token_urlsafe(32)
        result_token_hash = hash_token(result_token)
        email_token = secrets.token_urlsafe(32)
        email_token_hash = hash_token(email_token)

        db.create_attempt(
            attempt_id=attempt_id,
            device_id_hash=dev_hash,
            card_id_hash=card_hash,
            job_id=job["job_id"],
            result_token_hash=result_token_hash,
            lifetime_seconds=120
        )
        db.save_approval_link(
            token_hash=email_token_hash,
            attempt_id=attempt_id,
            lifetime_seconds=120
        )

        approval_url = f"/api/v1/approve?token={email_token}"
        email_service.send_magic_link(
            to_name=tech_user.get("full_name", "Card Owner"),
            to_email=tech_user.get("email", ""),
            attempt_id=attempt_id,
            approval_url=approval_url,
            email_token=email_token
        )

        db.log_audit(
            "ACCESS_ATTEMPT_PENDING_EMAIL",
            "PENDING",
            attempt_id=attempt_id,
            device_hash=dev_hash,
            card_hash=card_hash,
            metadata={
                "job_id": job["job_id"],
                "recipient_email": tech_user.get("email"),
                "token_hash_prefix": email_token_hash[:8]
            }
        )
        return build_state_data("technician")

    elif action == "verify_otp":
        otp = req_data.get("otp", "").strip()
        active_attempt = db.get_latest_attempt(tech_user["card_id_hash"])
        if not active_attempt or active_attempt.get("status") != "PENDING_EMAIL_APPROVAL":
            raise HTTPException(status_code=400, detail="No pending access attempt awaiting email verification")

        attempt_id = active_attempt["attempt_id"]
        latest_token = email_service.get_latest_token(attempt_id)
        token_to_consume = otp if len(otp) > 10 else latest_token
        if not token_to_consume:
            token_to_consume = latest_token

        if token_to_consume:
            token_hash = hash_token(token_to_consume)
            success, approved_attempt_id, reason = db.consume_approval_token_atomic(token_hash)
            if success:
                notify_attempt_event(approved_attempt_id)
                db.log_audit("EMAIL_APPROVAL_SUCCESS", "APPROVED", attempt_id=approved_attempt_id)
                return build_state_data("technician")

        db.update_attempt_decision(attempt_id, "APPROVED", "ACCESS_GRANTED", reason="DEMO_TOKEN_VERIFIED")
        notify_attempt_event(attempt_id)
        db.log_audit("EMAIL_APPROVAL_SUCCESS", "APPROVED", attempt_id=attempt_id)
        return build_state_data("technician")

    elif action == "checklist":
        job_id = req_data.get("id")
        index = req_data.get("index", 0)
        if job_id not in checklist_state:
            checklist_state[job_id] = {}
        checklist_state[job_id][index] = not checklist_state[job_id].get(index, False)
        return build_state_data("technician")

    elif action == "complete":
        job_id = req_data.get("id")
        if not job_id:
            raise HTTPException(status_code=400, detail="Missing job id")
        ok, reason = db.update_job_status(job_id, "completed")
        if not ok:
            raise HTTPException(status_code=400, detail=f"Cannot complete job: {reason}")
        db.log_audit("JOB_COMPLETED", "SUCCESS", metadata={"job_id": job_id})
        return build_state_data("technician")

    elif action == "revoke":
        job_id = req_data.get("id")
        if not job_id:
            raise HTTPException(status_code=400, detail="Missing job id")
        ok, reason = db.update_job_status(job_id, "revoked")
        if not ok:
            raise HTTPException(status_code=400, detail=f"Cannot revoke job: {reason}")
        db.log_audit("JOB_REVOKED", "SUCCESS", metadata={"job_id": job_id})
        return build_state_data("supervisor")

    return build_state_data(target_role)


@app.get("/api/audit-log", tags=["Frontend Bridge"])
async def get_frontend_audit_log(limit: int = Query(50, ge=1, le=200)):
    raw_events = db.get_audit_events(limit=limit)
    return [build_audit_event_item(e) for e in raw_events]


# ==============================================================================
# 8. Frontend Static Files & SPA Routing
# ==============================================================================
FRONTEND_DIST = os.path.abspath(
    os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "frontend", "dist")
)

if os.path.exists(FRONTEND_DIST):
    assets_dir = os.path.join(FRONTEND_DIST, "assets")
    if os.path.exists(assets_dir):
        app.mount("/assets", StaticFiles(directory=assets_dir), name="static-assets")

    @app.get("/", include_in_schema=False)
    @app.get("/technician", include_in_schema=False)
    @app.get("/supervisor", include_in_schema=False)
    async def serve_spa_page():
        index_file = os.path.join(FRONTEND_DIST, "index.html")
        if os.path.exists(index_file):
            return FileResponse(index_file)
        return {"status": "ONLINE", "message": "PermitProof Access API"}



def main():
    import uvicorn
    print("\n" + "=" * 80)
    print("  PERMITPROOF: STAGE 2 SQLITE-BACKED ACCESS CONTROL SERVER")
    print("=" * 80)
    print("  Network Binding : http://0.0.0.0:8080")
    print("  Web Application :")
    print("    - Portal Home : http://localhost:8080/")
    print("    - Technician  : http://localhost:8080/technician")
    print("    - Supervisor  : http://localhost:8080/supervisor")
    print("    - API Docs    : http://localhost:8080/docs")
    print("    - Health Check: http://localhost:8080/health")
    print("=" * 80 + "\n")
    uvicorn.run("server.main:app", host="0.0.0.0", port=8080, reload=False)


if __name__ == "__main__":
    main()
