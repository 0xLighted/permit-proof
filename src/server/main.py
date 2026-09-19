"""
Track 3 - Stage 1: Telemetry Ingestion API Server
Framework: FastAPI + Uvicorn
Objective: Ingest telemetry data from edge devices (Raspberry Pi) and display real-time metrics on the terminal.
"""

from fastapi import FastAPI, Request, status
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, Dict, Any, List
from datetime import datetime
import uvicorn
import time

app = FastAPI(
    title="Track 3 Telemetry Receiver",
    description="Stage 1: Telemetry Ingestion & Real-Time Terminal Monitoring",
    version="1.0.0"
)

# In-memory storage for recent telemetry data
telemetry_history: List[Dict[str, Any]] = []
MAX_HISTORY = 100

class TelemetryPayload(BaseModel):
    device_id: str = Field(..., description="Unique identifier for the edge device (e.g. charlie-pi-01)")
    timestamp: float = Field(default_factory=time.time, description="Unix timestamp of transmission")
    seq: int = Field(default=1, description="Monotonically increasing sequence number")
    temperature: Optional[float] = Field(None, description="Temperature reading in Celsius")
    humidity: Optional[float] = Field(None, description="Relative humidity percentage")
    cpu_load: Optional[float] = Field(None, description="Edge device CPU load percentage")
    memory_usage: Optional[float] = Field(None, description="Edge device RAM usage percentage")
    voltage: Optional[float] = Field(None, description="Supply or battery voltage")
    extra: Optional[Dict[str, Any]] = Field(default=None, description="Additional arbitrary sensor readings")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "device_id": "charlie-pi-01",
                "timestamp": 1726720000.0,
                "seq": 42,
                "temperature": 48.5,
                "humidity": 55.2,
                "cpu_load": 18.0,
                "memory_usage": 35.4,
                "voltage": 5.12
            }
        }
    )

def print_telemetry_terminal(payload: TelemetryPayload, client_ip: str, latency_ms: float):
    """
    Renders formatted, clear telemetry updates in the terminal.
    """
    # ANSI Color escapes for terminal styling
    CYAN = "\033[96m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    MAGENTA = "\033[95m"
    BOLD = "\033[1m"
    RESET = "\033[0m"

    received_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    
    temp_str = f"{payload.temperature:.1f} °C" if payload.temperature is not None else "N/A"
    hum_str = f"{payload.humidity:.1f} %" if payload.humidity is not None else "N/A"
    cpu_str = f"{payload.cpu_load:.1f} %" if payload.cpu_load is not None else "N/A"
    mem_str = f"{payload.memory_usage:.1f} %" if payload.memory_usage is not None else "N/A"
    volt_str = f"{payload.voltage:.2f} V" if payload.voltage is not None else "N/A"

    print(f"{CYAN}--------------------------------------------------------------------------------{RESET}")
    print(f"{BOLD}[TELEMETRY RECEIVED]{RESET} {GREEN}{received_time}{RESET} | Source: {YELLOW}{client_ip}{RESET}")
    print(f"  Device ID : {BOLD}{payload.device_id}{RESET} (Seq #{payload.seq})")
    print(f"  Sensors   : Temp: {MAGENTA}{temp_str}{RESET} | Humidity: {CYAN}{hum_str}{RESET} | Voltage: {volt_str}")
    print(f"  Metrics   : CPU: {YELLOW}{cpu_str}{RESET} | Memory: {CYAN}{mem_str}{RESET}")
    if payload.extra:
        print(f"  Extra     : {payload.extra}")
    print(f"{CYAN}--------------------------------------------------------------------------------{RESET}")


@app.get("/", tags=["Health"])
async def root():
    return {
        "status": "ONLINE",
        "service": "Track 3 Telemetry API Server",
        "stage": "Stage 1 - Connectivity",
        "total_records_received": len(telemetry_history),
        "server_time": datetime.now().isoformat()
    }


@app.post("/api/telemetry", status_code=status.HTTP_201_CREATED, tags=["Telemetry"])
async def ingest_telemetry(payload: TelemetryPayload, request: Request):
    t_start = time.time()
    client_ip = request.client.host if request.client else "unknown"
    
    # Store record
    record = payload.model_dump()
    record["received_at"] = time.time()
    record["client_ip"] = client_ip
    
    telemetry_history.append(record)
    if len(telemetry_history) > MAX_HISTORY:
        telemetry_history.pop(0)

    # Print to terminal
    latency_ms = (time.time() - t_start) * 1000.0
    print_telemetry_terminal(payload, client_ip, latency_ms)

    return {
        "status": "SUCCESS",
        "message": "Telemetry received and recorded",
        "device_id": payload.device_id,
        "seq": payload.seq,
        "timestamp": payload.timestamp
    }


@app.get("/api/telemetry", tags=["Telemetry"])
async def get_recent_telemetry(limit: int = 10):
    """Retrieve the most recent telemetry readings."""
    return telemetry_history[-limit:]


def main():
    print("\n" + "=" * 80)
    print("  TRACK 3: TELEMETRY INGESTION SERVER (Stage 1)")
    print("  Listening on: http://0.0.0.0:8080")
    print("  API Docs    : http://0.0.0.0:8080/docs")
    print("=" * 80 + "\n")
    uvicorn.run(app, host="0.0.0.0", port=8080)


if __name__ == "__main__":
    main()
