"""
PermitProof - Stage 2 Pydantic Schemas
Strict request and response contracts for the access API.
"""

from pydantic import BaseModel, Field, field_validator, ConfigDict
from typing import List, Optional
import re

HEX_64_PATTERN = re.compile(r"^[0-9a-f]{64}$")


class ChallengeResponse(BaseModel):
    nonce: str = Field(..., description="Cryptographically random URL-safe challenge nonce")
    expires_in_seconds: int = Field(default=30, description="Challenge lifetime in seconds")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "nonce": "k9L0v2R_mP8xQ1wZ4yT7uA",
                "expires_in_seconds": 30
            }
        }
    )


class AccessAttemptRequest(BaseModel):
    device_id_hash: str = Field(..., description="64-hex lowercase keyed device hash")
    card_id_hash: str = Field(..., description="64-hex lowercase keyed card UID hash")
    nonce: str = Field(..., description="Exact server-issued challenge nonce")
    message_hmac: str = Field(..., description="64-hex lowercase message HMAC over canonical signing bytes")

    @field_validator("device_id_hash", "card_id_hash", "message_hmac")
    @classmethod
    def validate_hex64(cls, v: str) -> str:
        if not isinstance(v, str) or not HEX_64_PATTERN.match(v):
            raise ValueError("Must be exactly 64 lowercase hexadecimal characters")
        return v

    @field_validator("nonce")
    @classmethod
    def validate_nonce(cls, v: str) -> str:
        if not v or "\n" in v or "\r" in v:
            raise ValueError("Nonce must be non-empty and must not contain newlines")
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "device_id_hash": "a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90",
                "card_id_hash": "b2c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90a1",
                "nonce": "k9L0v2R_mP8xQ1wZ4yT7uA",
                "message_hmac": "c3d4e5f60718293a4b5c6d7e8f90a1b2c3d4e5f60718293a4b5c6d7e8f90a1b2"
            }
        }
    )


class AccessAttemptResponse(BaseModel):
    attempt_id: str = Field(..., description="Opaque UUID identifying the access attempt")
    status: str = Field(default="PENDING_EMAIL_APPROVAL", description="Initial attempt status")
    result_token: str = Field(..., description="Single-use private token for Pi held GET")
    expires_in_seconds: int = Field(default=120, description="Email approval deadline in seconds")


class AttemptResultResponse(BaseModel):
    attempt_id: str = Field(..., description="Access attempt UUID")
    status: str = Field(..., description="Terminal state: APPROVED, REJECTED, or EXPIRED")
    decision: str = Field(..., description="Decision: ACCESS_GRANTED or ACCESS_DENIED")


class JobCreateRequest(BaseModel):
    job_id: Optional[str] = Field(None, description="Optional custom job ID (defaults to UUID)")
    supervisor_id: str = Field(..., description="64-hex card hash of supervisor")
    technician_id: str = Field(..., description="64-hex card hash of assigned technician")
    device_id_hash: str = Field(..., description="64-hex device hash of the target room reader")
    tasks: List[str] = Field(default_factory=list, description="List of inspection tasks")


class JobResponse(BaseModel):
    job_id: str
    created_at: float
    supervisor_id: str
    technician_id: str
    device_id_hash: str
    tasks: List[str]
    status: str
    is_complete: int
    accepted_at: Optional[float] = None
    completed_at: Optional[float] = None
    revoked_at: Optional[float] = None


class JobActionRequest(BaseModel):
    technician_id: Optional[str] = Field(None, description="64-hex card hash of technician performing action")

