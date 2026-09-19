"""Number 1 contracts. Mock events are explicitly labelled, never signed claims."""
from typing import Literal
from uuid import UUID
from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Event(StrictModel):
    event_id: str
    device_id: str = Field(min_length=1, max_length=64)
    observed_at_ms: int = Field(gt=0)
    source: Literal["mock", "hardware"]
    kind: Literal["nfc_tapped", "button_pressed", "session_reset"]
    uid: str | None = None

    @model_validator(mode="after")
    def validate_event(self):
        UUID(self.event_id)
        if self.kind == "nfc_tapped":
            if self.uid is None or not (1 <= len(self.uid) <= 64):
                raise ValueError("An NFC event requires uid (1–64 characters)")
        elif self.uid is not None:
            raise ValueError("Only NFC events may contain uid")
        if self.kind == "session_reset" and self.source != "mock":
            raise ValueError("Reset is a mock-only action")
        return self


class Person(StrictModel):
    id: str
    name: str
    role: str
    can_inspect: bool


class DesiredState(StrictModel):
    device_id: str
    revision: int = 0
    phase: Literal["idle", "ready", "active", "complete", "denied"] = "idle"
    led: Literal["white", "blue", "green", "yellow", "red"] = "white"
    lcd_pages: list[list[str]] = Field(default_factory=lambda: [["MOCK WORKFLOW", "Tap a card"]])
    person: Person | None = None
    session_id: str | None = None
    workflow_mode: Literal["mock"] = "mock"


class Report(StrictModel):
    device_id: str
    revision: int = Field(ge=0)
    outputs: Literal["mock", "hardware"]
    applied: bool
    observed_at_ms: int = Field(gt=0)
    error: str | None = Field(default=None, max_length=200)
    lcd_backend: Literal["console", "i2c"] = "console"

    @model_validator(mode="after")
    def validate_report(self):
        if self.applied and self.error:
            raise ValueError("A successful report cannot include an error")
        if not self.applied and not self.error:
            raise ValueError("A failed report requires an error")
        if self.outputs == "mock" and self.lcd_backend != "console":
            raise ValueError("Mock outputs cannot claim I2C LCD application")
        return self
