"""Canonical vehicle events shared by simulation and future STM32/ESP32 input."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

# Event types — STM32 firmware should reuse the same names when it reports.
BATTERY_FAULT_DETECTED = "BATTERY_FAULT_DETECTED"
ENGINE_FAULT_DETECTED = "ENGINE_FAULT_DETECTED"
BRAKE_FAULT_DETECTED = "BRAKE_FAULT_DETECTED"
STEERING_FAULT_DETECTED = "STEERING_FAULT_DETECTED"
CLIMATE_FAULT_DETECTED = "CLIMATE_FAULT_DETECTED"
ADAS_FAULT_DETECTED = "ADAS_FAULT_DETECTED"
COMM_FAULT_DETECTED = "COMM_GATEWAY_FAULT_DETECTED"

ECU_RECOVERY_STARTED = "ECU_RECOVERY_STARTED"
ECU_RECOVERY_SUCCESS = "ECU_RECOVERY_SUCCESS"
ECU_RECOVERY_FAILED = "ECU_RECOVERY_FAILED"

OTA_STARTED = "OTA_STARTED"
OTA_COMPLETED = "OTA_COMPLETED"
OTA_FAILED = "OTA_FAILED"

CAN_ERROR = "CAN_ERROR"
CAN_FRAME = "CAN_FRAME"

VEHICLE_CONNECTED = "VEHICLE_CONNECTED"
VEHICLE_DISCONNECTED = "VEHICLE_DISCONNECTED"
MODE_CHANGED = "MODE_CHANGED"

DIAGNOSTIC_CREATED = "DIAGNOSTIC_CREATED"
ECU_STATE_CHANGED = "ECU_STATE_CHANGED"
TELEMETRY_SAMPLE = "TELEMETRY_SAMPLE"
VOICE_COMMAND = "VOICE_COMMAND"
SYSTEM_LOG = "SYSTEM_LOG"

FAULT_EVENT_BY_ECU = {
    "engine": ENGINE_FAULT_DETECTED,
    "battery": BATTERY_FAULT_DETECTED,
    "brake": BRAKE_FAULT_DETECTED,
    "steering": STEERING_FAULT_DETECTED,
    "climate": CLIMATE_FAULT_DETECTED,
    "adas": ADAS_FAULT_DETECTED,
    "communication": COMM_FAULT_DETECTED,
}


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


@dataclass
class VehicleEvent:
    """One engineering event. All modules consume this shape — never page-to-page calls."""

    event_type: str
    timestamp: str
    ecu: str | None
    severity: str
    payload: dict[str, Any]
    source: str
    correlation_id: str = field(default_factory=lambda: str(uuid4())[:12])

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "timestamp": self.timestamp,
            "ecu": self.ecu,
            "severity": self.severity,
            "payload": self.payload,
            "source": self.source,
            "correlation_id": self.correlation_id,
        }

    @classmethod
    def create(
        cls,
        event_type: str,
        *,
        source: str,
        ecu: str | None = None,
        severity: str = "INFO",
        payload: dict[str, Any] | None = None,
        correlation_id: str | None = None,
    ) -> VehicleEvent:
        event = cls(
            event_type=event_type,
            timestamp=utc_now_iso(),
            ecu=ecu,
            severity=severity,
            payload=payload or {},
            source=source,
        )
        if correlation_id:
            event.correlation_id = correlation_id
        return event
