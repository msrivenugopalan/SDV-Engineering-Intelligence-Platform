"""Shared data models. UI and REST serialize these; they are not Tk widgets."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class ECUState:
    id: str
    name: str
    task_name: str
    responsibility: str
    status: str
    health: int
    last_update: str
    fault_id: str | None
    recovery_state: str
    task_state: str
    last_event: str
    can_id: int
    message_name: str
    telemetry: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DiagnosticRecord:
    fault_id: str
    ecu: str
    detected_time: str
    severity: str
    description: str
    possible_cause: str
    diagnostic_status: str
    recovery_status: str
    confidence: int
    recommended_action: str
    evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RecoveryStep:
    name: str
    status: str  # PENDING | ACTIVE | DONE | FAILED
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ARISession:
    ecu: str
    fault_id: str
    correlation_id: str
    started_at: str
    result: str  # IN_PROGRESS | SUCCESS | FAILED | IDLE
    steps: list[RecoveryStep] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "ecu": self.ecu,
            "fault_id": self.fault_id,
            "correlation_id": self.correlation_id,
            "started_at": self.started_at,
            "result": self.result,
            "steps": [s.to_dict() for s in self.steps],
        }


@dataclass
class OTASession:
    current_version: str
    target_version: str
    target_ecu: str
    status: str
    progress: int
    started_at: str | None = None
    finished_at: str | None = None
    result: str = ""
    checks: dict[str, bool] = field(default_factory=dict)
    stages: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CANFrame:
    timestamp: str
    can_id: str
    ecu: str
    message: str
    data: str
    direction: str
    status: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CANBusStatus:
    bus_state: str
    message_count: int
    error_count: int
    last_message: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
