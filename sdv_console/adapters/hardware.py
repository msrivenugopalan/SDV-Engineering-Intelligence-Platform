
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

ECU_HEARTBEAT_TIMEOUT_S = 3.0

ECU_HEARTBEAT_FIELDS = {
    "engine": "engine_ecu_ms",
    "battery": "battery_ecu_ms",
    "brake": "brake_ecu_ms",
    "steering": "steering_ecu_ms",
    "climate": "climate_ecu_ms",
    "adas": "adas_ecu_ms",
}

ECU_HEARTBEAT_FAULT_ID = "ECU_HEARTBEAT_TIMEOUT"


# Fields that the current STM32 firmware does not transmit.
# Clear their initial demo values when hardware telemetry first arrives.
HARDWARE_UNAVAILABLE_FIELDS = (
    "battery_current",
    "battery_power",
    "estimated_range",
    "vehicle_state",
)


class HardwareAdapter(VehicleSource):
    name = "hardware"

    
    def __init__(self, state: VehicleState, events: EventBus) -> None:
        self.state = state
        self.events = events
        self._connected = False
        self._last_seen: float | None = None
        self._last_seen_by_transport: dict[str, float] = {}
        self._hardware_telemetry_initialized = False
        
        self._heartbeat_last_value: dict[str, int] = {}
        self._heartbeat_last_progress: dict[str, float] = {}
        self._heartbeat_timed_out: set[str] = set()
        self._heartbeat_previous_state: dict[str, dict[str, Any]] = {}


    @property
    def connected(self) -> bool:
        return self._connected

    def start(self) -> None:
        pass  # Receive-driven adapter; no polling required.

    def stop(self) -> None:
        self._last_seen_by_transport.clear()
        self._last_seen = None
        self._update_connection_state()

    def tick(self, dt: float) -> None:
        now = time.monotonic()

        # Expire each transport independently.
        self._last_seen_by_transport = {
            transport: timestamp
            for transport, timestamp
            in self._last_seen_by_transport.items()
            if now - timestamp <= LINK_TIMEOUT_S
        }

        self._last_seen = max(
            self._last_seen_by_transport.values(),
            default=None,
        )
        self._update_connection_state()

    def _update_connection_state(self) -> None:
        active = self._last_seen_by_transport

        # MQTT traffic alone does not prove either physical device is linked.
        stm32_connected = (
            "serial" in active or "esp32" in active
        )
        esp32_connected = "esp32" in active

        # The gateway transport is treated as carrying STM32-originated
        # messages in this prototype. This is not cryptographic verification.
        changed = (stm32_connected or esp32_connected) != self._connected
        self._connected = stm32_connected or esp32_connected

        self.state.set_service(
            stm32=stm32_connected,
            esp32=esp32_connected,
        )

        if changed:
            self.events.publish(
                VehicleEvent.create(
                    "VEHICLE_CONNECTED"
                    if self._connected
                    else "VEHICLE_DISCONNECTED",
                    source="hardware",
                    severity="INFO"
                    if self._connected
                    else "WARNING",
                    payload={
                        "message": (
                            "Hardware telemetry transport active."
                            if self._connected
                            else "Hardware telemetry transports inactive."
                        )
                    },
                )
            )


    
    def ingest(
        self,
        message: dict[str, Any],
        transport: str = "serial",
    ) -> None:
        kind = message.get("type")

        # Ignore unknown message types rather than treating them as valid
        # vehicle telemetry.
        if kind not in {"telemetry", "ecu", "can", "event"}:
            return

        if transport not in {"serial", "esp32", "mqtt"}:
            return

        now = time.monotonic()
        self._last_seen_by_transport[transport] = now
        self._last_seen = now
        self._update_connection_state()

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
            
            self._process_ecu_heartbeats(values, now)


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

    def _process_ecu_heartbeats(
            self, values: dict[str, Any], now: float
        ) -> None:
            snapshot = self.state.snapshot()
            ecus = snapshot.get("ecus", {})
            diagnostics = snapshot.get("diagnostics", [])
    
            for ecu_id, field in ECU_HEARTBEAT_FIELDS.items():
                value = values.get(field)
    
                # Ignore missing or invalid heartbeat values.
                if (
                    not isinstance(value, int)
                    or isinstance(value, bool)
                    or not 0 <= value <= 0xFFFFFFFF
                ):
                    continue
    
                previous = self._heartbeat_last_value.get(ecu_id)
    
                if previous is None:
                    self._heartbeat_last_value[ecu_id] = value
                    self._heartbeat_last_progress[ecu_id] = now
                    continue
    
                # Unsigned 32-bit subtraction handles HAL_GetTick rollover.
                delta = (value - previous) & 0xFFFFFFFF
    
                # Accept forward progress, including rollover, but ignore
                # duplicate values and implausible backward/stale updates.
                if 0 < delta < 0x80000000:
                    self._heartbeat_last_value[ecu_id] = value
                    self._heartbeat_last_progress[ecu_id] = now
    
                    if ecu_id in self._heartbeat_timed_out:
                        self._heartbeat_timed_out.remove(ecu_id)
    
                        previous_state = self._heartbeat_previous_state.pop(
                            ecu_id, {}
                        )
                        prior_status = previous_state.get(
                            "status", "HEALTHY"
                        )
                        prior_fault_id = previous_state.get("fault_id")
                        prior_health = previous_state.get("health", 100)
                        prior_event = previous_state.get(
                            "last_event", "Nominal"
                        )
    
                        # Clear only this monitor's diagnostic.
                        self.state.clear_diagnostic(
                            ecu_id, ECU_HEARTBEAT_FAULT_ID
                        )
    
                        # Preserve an ECU fault that existed before timeout.
                        self.state.update_ecu(
                            ecu_id,
                            status=prior_status,
                            fault_id=prior_fault_id,
                            health=prior_health,
                            last_event=prior_event,
                        )
    
                        self.events.publish(
                            VehicleEvent.create(
                                "ECU_HEARTBEAT_RESTORED",
                                source="hardware",
                                ecu=ecu_id,
                                severity="INFO",
                                payload={
                                    "message": (
                                        f"{ecu_id} heartbeat resumed."
                                    )
                                },
                            )
                        )
    
            # Evaluate timeout independently for each ECU.
            for ecu_id in ECU_HEARTBEAT_FIELDS:
                last_progress = self._heartbeat_last_progress.get(ecu_id)
    
                # Do not declare a fault until a valid heartbeat was observed.
                if last_progress is None:
                    continue
    
                if (
                    now - last_progress <= ECU_HEARTBEAT_TIMEOUT_S
                    or ecu_id in self._heartbeat_timed_out
                ):
                    continue
    
                ecu = ecus.get(ecu_id)
                if ecu is None:
                    continue
    
                self._heartbeat_previous_state[ecu_id] = {
                    "status": ecu.get("status", "HEALTHY"),
                    "fault_id": ecu.get("fault_id"),
                    "health": ecu.get("health", 100),
                    "last_event": ecu.get("last_event", "Nominal"),
                }
                self._heartbeat_timed_out.add(ecu_id)
    
                self.state.update_ecu(
                    ecu_id,
                    status="OFFLINE",
                    health=0,
                    fault_id=ECU_HEARTBEAT_FAULT_ID,
                    last_event="ECU heartbeat timeout",
                )
    
                # Do not create duplicate active heartbeat diagnostics.
                active_heartbeat_diagnostic = any(
                    d.get("ecu") == ecu_id
                    and d.get("fault_id") == ECU_HEARTBEAT_FAULT_ID
                    and d.get("status") == "ACTIVE"
                    for d in diagnostics
                )
    
                if not active_heartbeat_diagnostic:
                    self.state.add_diagnostic(
                        DiagnosticRecord(
                            dtc_id=new_id(),
                            ecu=ecu_id,
                            fault_id=ECU_HEARTBEAT_FAULT_ID,
                            severity="WARNING",
                            status="ACTIVE",
                            detected_at=utc_now_iso(),
                        )
                    )
    
                self.events.publish(
                    VehicleEvent.create(
                        "ECU_HEARTBEAT_TIMEOUT",
                        source="hardware",
                        ecu=ecu_id,
                        severity="WARNING",
                        payload={
                            "message": (
                                f"{ecu_id} heartbeat stopped advancing."
                            ),
                            "timeout_seconds": ECU_HEARTBEAT_TIMEOUT_S,
                        },
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
