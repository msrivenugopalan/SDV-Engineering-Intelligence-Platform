"""Dataclasses shared across state, adapters, services, and views.

These are the shapes that flow through Central State (see vehicle_state.py).
Every module reads/writes these — not its own parallel copy.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id() -> str:
    return uuid.uuid4().hex[:10]


@dataclass
class ECUState:
    id: str
    name: str
    task: str
    status: str = "OFFLINE"       # HEALTHY | WARNING | FAULT | RECOVERING | OFFLINE
    health: int = 0                # 0-100
    fault_id: str | None = None
    recovery_state: str = "IDLE"   # IDLE | AVAILABLE | IN_PROGRESS | RECOVERED
    firmware: str = "v1.0.0"
    last_event: str = "—"
    last_update: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CANFrame:
    timestamp: str
    can_id: str
    message: str
    ecu: str
    direction: str  # TX | RX
    status: str     # OK | ERROR
    data: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DiagnosticRecord:
    dtc_id: str
    ecu: str
    fault_id: str
    severity: str        # CRITICAL | WARNING | INFO
    status: str           # ACTIVE | RECOVERING | CLEARED
    detected_at: str
    cleared_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class OTASession:
    current_version: str
    target_version: str
    target_ecu: str
    status: str = "IDLE"   # IDLE | VALIDATING | DOWNLOADING | INSTALLING | COMPLETED | FAILED
    progress: int = 0
    checks: dict[str, bool] = field(default_factory=dict)
    started_at: str | None = None
    finished_at: str | None = None
    from_version: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RecoverySession:
    ecu: str
    fault_id: str
    status: str = "IDLE"  # IDLE | ACTIVE | SUCCESS | FAILED
    started_at: str | None = None
    finished_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class VehicleEvent:
    event_type: str
    source: str
    timestamp: str = field(default_factory=utc_now_iso)
    ecu: str | None = None
    severity: str = "INFO"
    payload: dict[str, Any] = field(default_factory=dict)
    correlation_id: str = field(default_factory=new_id)

    @classmethod
    def create(cls, event_type: str, **kwargs: Any) -> "VehicleEvent":
        return cls(event_type=event_type, **kwargs)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
