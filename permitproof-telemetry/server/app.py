"""Run with python -m server.app. Local-only Number 1 mock API."""
import json
import os
import secrets
from pathlib import Path
from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from contracts.schemas import Event, Report
from server.storage import Conflict, Store, StoreFull

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")


def create_app(store=None, token=None, device_id=None):
    token = token if token is not None else os.getenv("PERMITPROOF_TOKEN", "")
    if len(token) < 24:
        raise RuntimeError("Run python -m scripts.setup_local first (local token missing/too short)")
    device_id = device_id or os.getenv("PERMITPROOF_DEVICE_ID", "pi-001")
    store = store or Store(ROOT / os.getenv("PERMITPROOF_STORE", "runtime/mock-store.json"),
                           json.loads((ROOT / "data/mock_people.json").read_text()))
    app = FastAPI(title="PermitProof Number 1 — MOCK WORKFLOW", docs_url="/docs", redoc_url=None)
    auth = HTTPBearer(auto_error=False)

    @app.middleware("http")
    async def body_limit(request: Request, call_next):
        if request.method in ("POST", "PUT", "PATCH"):
            size = 0
            chunks = []
            async for chunk in request.stream():
                size += len(chunk)
                if size > 8192:
                    return JSONResponse({"detail": "Request exceeds 8 KiB lab limit"}, status_code=413)
                chunks.append(chunk)
            request._body = b"".join(chunks)
        return await call_next(request)

    def authorised(device_id: str, credentials: HTTPAuthorizationCredentials | None = Depends(auth)):
        if not credentials or not secrets.compare_digest(credentials.credentials, token):
            raise HTTPException(401, "Valid lab bearer token required")
        if device_id != app.state.device_id:
            raise HTTPException(403, "Token does not authorise this device")

    app.state.device_id = device_id

    @app.get("/health")
    def health():
        return {"status": "ok", "workflow_mode": "mock", "hardware_verified": False}

    @app.post("/api/v1/devices/{device_id}/events", dependencies=[Depends(authorised)])
    def events(device_id: str, event: Event):
        if event.device_id != device_id:
            raise HTTPException(403, "Path and payload device must match")
        try:
            return store.event(event)
        except Conflict as exc:
            raise HTTPException(409, str(exc)) from exc
        except StoreFull as exc:
            raise HTTPException(507, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(422, str(exc)) from exc

    @app.get("/api/v1/devices/{device_id}/desired-state", dependencies=[Depends(authorised)])
    def desired(device_id: str):
        return store.desired(device_id)

    @app.post("/api/v1/devices/{device_id}/reported-state", dependencies=[Depends(authorised)])
    def reported(device_id: str, report: Report):
        if report.device_id != device_id:
            raise HTTPException(403, "Path and payload device must match")
        try:
            store.report(report)
        except Conflict as exc:
            raise HTTPException(409, str(exc)) from exc
        return {"recorded": True, "revision": report.revision}

    @app.get("/api/v1/devices/{device_id}/status", dependencies=[Depends(authorised)])
    def status(device_id: str):
        return store.status(device_id)

    return app


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(create_app(), host="127.0.0.1", port=8000)
