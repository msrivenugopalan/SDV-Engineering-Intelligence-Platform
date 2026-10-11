
"""Hardware adapter — where real STM32/ESP32 data enters Central State.

Hardware telemetry is the source of truth in HARDWARE mode. Values not
provided by the hardware are marked unavailable instead of retaining
simulation/demo values.
"""

from __future__ import annotations

import time
from typing import Any

from sdv_console.adapters.base import VehicleSource
from sdv_console.core.event_bus import EventBus
from sdv_console.core.models import (
    DiagnosticRecord,
    VehicleEvent,
    new_id,
    utc_now_iso,
)
from sdv_console.core.vehicle_state import VehicleState

LINK_TIMEOUT_S = 5.0

# Fields that the current STM32 firmware does not transmit.
# Clear their initial demo values when hardware telemetry first arrives.
HARDWARE_UNAVAILABLE_FIELDS = (
    "battery_current",
    "battery_power",
    "estimated_range",
    "cabin_temp",
    "vehicle_state",
)


class HardwareAdapter(VehicleSource):
    name = "hardware"

    def __init__(self, state: VehicleState, events: EventBus) -> None:
        self.state = state
        self.events = events
        self._connected = False
        self._last_seen: float | None = None
        self._hardware_telemetry_initialized = False

    @property
    def connected(self) -> bool:
        return self._connected

    def start(self) -> None:
        pass  # Receive-driven adapter; no polling required.

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

        # Direct USB serial confirms the STM32 link only.
        # ESP32 remains disconnected until its gateway transport is integrated.
        self.state.set_service(stm32=connected, esp32=False)

        if changed:
            self.events.publish(
                VehicleEvent.create(
                    "VEHICLE_CONNECTED" if connected else "VEHICLE_DISCONNECTED",
                    source="hardware",
                    severity="INFO" if connected else "WARNING",
                    payload={
                        "message": (
                            "STM32 USB serial link established."
                            if connected
                            else "STM32 hardware link lost (timeout)."
                        )
                    },
                )
            )

    def ingest(self, message: dict[str, Any]) -> None:
        kind = message.get("type")

        # Ignore unknown message types rather than treating them as valid
        # vehicle telemetry.
        if kind not in {"telemetry", "ecu", "can", "event"}:
            return

        self._last_seen = time.monotonic()

        if not self._connected:
            self._set_connected(True)

        if kind == "telemetry":
            values = {
                key: value
                for key, value in message.items()
                if key not in {"type", "source"}
            }

            # On the first telemetry packet, remove stale demo values for
            # measurements not supplied by the current STM32 firmware.
            if not self._hardware_telemetry_initialized:
                unavailable = {
                    key: None for key in HARDWARE_UNAVAILABLE_FIELDS
                }
                self.state.update_telemetry(
                    unavailable, source="hardware"
                )
                self._hardware_telemetry_initialized = True

            # Store values actually received from the STM32.
            self.state.update_telemetry(values, source="hardware")

            # Derive vehicle state from actual received speed when available.
            speed = values.get("vehicle_speed")
            if (
                isinstance(speed, (int, float))
                and not isinstance(speed, bool)
            ):
                self.state.update_telemetry(
                    {
                        "vehicle_state": (
                            "RUNNING" if speed > 1 else "IDLE"
                        )
                    },
                    source="hardware",
                )

        elif kind == "ecu":
            ecu_id = str(message.get("ecu", ""))
            fields = {
                key: value
                for key, value in message.items()
                if key not in {"type", "ecu", "source"}
            }

            if ecu_id:
                self.state.update_ecu(ecu_id, **fields)

                if fields.get("status") == "FAULT":
                    self.state.add_diagnostic(
                        DiagnosticRecord(
                            dtc_id=new_id(),
                            ecu=ecu_id,
                            fault_id=str(
                                fields.get("fault_id", "HW_FAULT")
                            ),
                            severity=str(
                                fields.get("severity", "WARNING")
                            ),
                            status="ACTIVE",
                            detected_at=utc_now_iso(),
                        )
                    )

        elif kind == "can":
            from sdv_console.core.models import CANFrame

            frame = CANFrame(
                timestamp=utc_now_iso(),
                can_id=str(message.get("can_id", "0x000")),
                message=str(message.get("message", "Unknown")),
                ecu=str(message.get("ecu", "—")),
                direction=str(message.get("direction", "RX")),
                status=str(message.get("status", "OK")),
                data=str(message.get("data", "")),
            )
            self.state.add_can_frame(
                frame, error=frame.status == "ERROR"
            )

        elif kind == "event":
            self.events.publish(
                VehicleEvent.create(
                    str(message.get("event_type", "SYSTEM_LOG")),
                    source="hardware",
                    ecu=message.get("ecu"),
                    severity=str(message.get("severity", "INFO")),
                    payload=message.get("payload") or {},
                )
            )

    def inject_fault(self, ecu_id: str) -> dict[str, Any]:
        return {
            "ok": False,
            "error": "hardware_read_only",
            "detail": (
                "Hardware fault injection is not implemented in firmware yet."
            ),
        }

    def start_recovery(self, ecu_id: str) -> dict[str, Any]:
        return {"ok": False, "error": "hardware_read_only"}

    def start_ota(
        self, target_ecu: str, target_version: str
    ) -> dict[str, Any]:
        return {
            "ok": False,
            "error": "hardware_read_only",
            "detail": (
                "Hardware OTA requires the ESP32 gateway and STM32 "
                "bootloader integration."
            ),
        }
