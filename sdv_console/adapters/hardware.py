"""Hardware adapter — where real STM32/ESP32 data enters Central State.

`ingest()` is the single seam between "real hardware" and everything else
in this app. REST's POST /hardware/ingest and the MQTT bridge both end up
calling this same method with the same JSON shape — Central State, and
every view built on it, doesn't know or care which transport it came from.

Until a message actually arrives here, `connected` stays False and
SIMULATION MODE is what drives the console. That's not a placeholder for
show — it's the literal switch this project is built around (architecture
doc §18, "Simulation vs Hardware Mode").
"""

from __future__ import annotations

import time
from typing import Any

from sdv_console.adapters.base import VehicleSource
from sdv_console.core.event_bus import EventBus
from sdv_console.core.models import DiagnosticRecord, VehicleEvent, new_id, utc_now_iso
from sdv_console.core.vehicle_state import VehicleState

LINK_TIMEOUT_S = 5.0

# Expected JSON shapes (mirror these in ESP32/STM32 firmware):
#   {"type": "telemetry", "engine_temp": 91.4, "battery_voltage": 12.7, ...}
#   {"type": "ecu", "ecu": "battery", "status": "FAULT", "health": 40}
#   {"type": "can", "can_id": "0x102", "message": "BatteryStatus", "ecu": "battery",
#    "direction": "RX", "status": "OK", "data": "V=12.6"}
#   {"type": "event", "event_type": "FAULT_DETECTED", "ecu": "battery",
#    "severity": "WARNING", "payload": {"fault_id": "BATT_TEMP_HIGH"}}


class HardwareAdapter(VehicleSource):
    name = "hardware"

    def __init__(self, state: VehicleState, events: EventBus) -> None:
        self.state = state
        self.events = events
        self._connected = False
        self._last_seen: float | None = None

    @property
    def connected(self) -> bool:
        return self._connected

    def start(self) -> None:
        pass  # nothing to poll — this adapter is purely receive-driven

    def stop(self) -> None:
        self._set_connected(False)
        self._last_seen = None

    def tick(self, dt: float) -> None:
        if self._connected and self._last_seen is not None:
            if time.monotonic() - self._last_seen > LINK_TIMEOUT_S:
                self._set_connected(False)

    def _set_connected(self, connected: bool) -> None:
        changed = connected != self._connected
        self._connected = connected
        self.state.set_service(stm32=connected, esp32=connected)
        if changed:
            self.events.publish(VehicleEvent.create(
                "VEHICLE_CONNECTED" if connected else "VEHICLE_DISCONNECTED",
                source="hardware", severity="INFO" if connected else "WARNING",
                payload={"message": "STM32/ESP32 link established." if connected else "STM32/ESP32 link lost (timeout)."},
            ))

    def ingest(self, message: dict[str, Any]) -> None:
        self._last_seen = time.monotonic()
        if not self._connected:
            self._set_connected(True)

        kind = message.get("type")
        if kind == "telemetry":
            values = {k: v for k, v in message.items() if k not in {"type", "source"}}
            self.state.update_telemetry(values, source="hardware")
        elif kind == "ecu":
            ecu_id = str(message.get("ecu", ""))
            fields = {k: v for k, v in message.items() if k not in {"type", "ecu", "source"}}
            if ecu_id:
                self.state.update_ecu(ecu_id, **fields)
                if fields.get("status") == "FAULT":
                    self.state.add_diagnostic(DiagnosticRecord(
                        dtc_id=new_id(), ecu=ecu_id, fault_id=str(fields.get("fault_id", "HW_FAULT")),
                        severity=str(fields.get("severity", "WARNING")), status="ACTIVE", detected_at=utc_now_iso(),
                    ))
        elif kind == "can":
            from sdv_console.core.models import CANFrame
            frame = CANFrame(
                timestamp=utc_now_iso(), can_id=str(message.get("can_id", "0x000")),
                message=str(message.get("message", "Unknown")), ecu=str(message.get("ecu", "—")),
                direction=str(message.get("direction", "RX")), status=str(message.get("status", "OK")),
                data=str(message.get("data", "")),
            )
            self.state.add_can_frame(frame, error=frame.status == "ERROR")
        elif kind == "event":
            self.events.publish(VehicleEvent.create(
                str(message.get("event_type", "SYSTEM_LOG")), source="hardware",
                ecu=message.get("ecu"), severity=str(message.get("severity", "INFO")),
                payload=message.get("payload") or {},
            ))

    def inject_fault(self, ecu_id: str) -> dict[str, Any]:
        return {"ok": False, "error": "hardware_read_only", "detail": "Fault injection over hardware isn't wired to firmware yet — inject via REST/MQTT command topics once the STM32 side implements it."}

    def start_recovery(self, ecu_id: str) -> dict[str, Any]:
        return {"ok": False, "error": "hardware_read_only"}

    def start_ota(self, target_ecu: str, target_version: str) -> dict[str, Any]:
        return {"ok": False, "error": "hardware_read_only", "detail": "OTA-over-hardware needs the ESP32 gateway + STM32 bootloader side implemented first."}
