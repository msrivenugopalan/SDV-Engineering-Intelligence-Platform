"""Hardware adapter — STM32 Nucleo-F446RE via ESP32 gateway.

This is an interface, not a fake live link. Methods encode the JSON/UART
contract in firmware/PROTOCOL.md. Until a socket/serial path is open,
commands return `hardware_unavailable` and the console stays honest.
"""

from __future__ import annotations

from typing import Any

from sdv_console.adapters.base import VehicleSource
from sdv_console.core.event_manager import EventManager
from sdv_console.core.events import SYSTEM_LOG, VehicleEvent
from sdv_console.core.vehicle_state import VehicleStateManager


class HardwareAdapter(VehicleSource):
    name = "hardware"

    def __init__(self, state: VehicleStateManager, events: EventManager) -> None:
        self.state = state
        self.events = events
        self._connected = False

    @property
    def connected(self) -> bool:
        return self._connected

    def start(self) -> None:
        # Future: open serial to ESP32 or subscribe MQTT sdv/esp32/#
        self._log("Hardware adapter idle — no STM32/ESP32 link configured.")

    def stop(self) -> None:
        self._connected = False
        self.state.set_service_flags(stm32=False, esp32=False)

    def ingest(self, message: dict[str, Any]) -> None:
        """Called when ESP32/MQTT delivers a JSON payload from the STM32.

        Expected shapes are documented in firmware/PROTOCOL.md. This method
        is the only place UI-adjacent code should ever meet raw hardware JSON.
        """
        msg_type = message.get("type")
        if msg_type == "telemetry":
            values = {k: v for k, v in message.items() if k not in {"type", "source"}}
            self.state.update_telemetry(values, source="hardware")
        elif msg_type == "event":
            self.events.publish(
                VehicleEvent.create(
                    str(message.get("event_type", "SYSTEM_LOG")),
                    source="hardware",
                    ecu=message.get("ecu"),
                    severity=str(message.get("severity", "INFO")),
                    payload=message.get("payload") or {},
                )
            )
        elif msg_type == "ecu":
            ecu_id = str(message.get("ecu", ""))
            fields = {k: v for k, v in message.items() if k not in {"type", "ecu", "source"}}
            if ecu_id:
                self.state.update_ecu(ecu_id, **fields)

    def tick(self, dt: float) -> None:
        return

    def inject_fault(self, ecu_id: str, correlation_id: str | None = None) -> dict[str, Any]:
        if not self._connected:
            return {
                "ok": False,
                "error": "hardware_unavailable",
                "detail": "STM32 is not connected. Fault inject would be sent UART/MQTT: "
                '{"type":"command","command":"fault_inject","ecu":"%s"}' % ecu_id,
            }
        return {"ok": True, "queued": True, "ecu": ecu_id}

    def start_recovery(self, ecu_id: str | None = None) -> dict[str, Any]:
        if not self._connected:
            return {"ok": False, "error": "hardware_unavailable"}
        return {"ok": True, "queued": True}

    def start_ota(self, target_ecu: str, target_version: str) -> dict[str, Any]:
        if not self._connected:
            return {"ok": False, "error": "hardware_unavailable"}
        return {"ok": True, "queued": True}

    def _log(self, text: str) -> None:
        self.events.publish(VehicleEvent.create(SYSTEM_LOG, source="hardware", payload={"message": text}))
