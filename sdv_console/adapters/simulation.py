"""Simulation adapter — the "Simulation Engine" box in the architecture doc.

Everything here writes into Central State and the Event Bus through the
exact same calls Hardware would use (see adapters/hardware.py). No view
ever touches this module directly — only EngineeringPlatform does.
"""

from __future__ import annotations

import random
from typing import Any

from sdv_console.adapters.base import VehicleSource
from sdv_console.config import FAULT_CATALOG
from sdv_console.core.event_bus import EventBus
from sdv_console.core.models import CANFrame, DiagnosticRecord, VehicleEvent, new_id, utc_now_iso
from sdv_console.core.vehicle_state import VehicleState

RECOVERY_DURATION_S = 2.5


class SimulationAdapter(VehicleSource):
    name = "simulation"

    def __init__(self, state: VehicleState, events: EventBus) -> None:
        self.state = state
        self.events = events
        self._running = False
        self._rng = random.Random(42)
        self._recovery_elapsed = 0.0
        self._recovery_active = False
        self._recovery_ecu: str | None = None

    def start(self) -> None:
        self._running = True
        self.state.set_mode("SIMULATION", "Simulation", source="simulation")
        self.state.restore_all_ecus(source="simulation")
        self.events.publish(VehicleEvent.create(
            "SYSTEM_LOG", source="simulation",
            payload={"message": "Simulation started — telemetry and CAN traffic are software-generated, not STM32 sensor data."},
        ))

    def stop(self) -> None:
        self._running = False
        self.state.set_mode("DISCONNECTED", "Disconnected", source="simulation")
        self.state.disconnect_all_ecus()

    def tick(self, dt: float) -> None:
        if not self._running or self.state.paused:
            return
        snap = self.state.snapshot()
        telemetry = dict(snap["telemetry"])
        self._nudge(telemetry, snap["ecus"])
        self.state.update_telemetry(telemetry, source="simulation")

        for ecu_id, ecu in snap["ecus"].items():
            fault = ecu["status"] in {"FAULT", "RECOVERING"}
            frame = self._make_frame(ecu_id, ecu["name"], telemetry, fault)
            self.state.add_can_frame(frame, error=fault and ecu["status"] == "FAULT")

        self.state.tick_can_rate(dt)
        self._tick_recovery(dt)

    # ------------------------------------------------------------ noise --

    def _nudge(self, t: dict[str, Any], ecus: dict) -> None:
        battery_fault = ecus.get("battery", {}).get("status") in {"FAULT", "RECOVERING"}
        engine_fault = ecus.get("engine", {}).get("status") in {"FAULT", "RECOVERING"}
        climate_fault = ecus.get("climate", {}).get("status") in {"FAULT", "RECOVERING"}

        if not engine_fault:
            t["engine_temp"] = round(self._clamp(t.get("engine_temp", 86), 84, 92, 0.15), 1)
            t["vehicle_speed"] = round(self._clamp(t.get("vehicle_speed", 48), 32, 64, 0.5), 1)
        else:
            t["vehicle_speed"] = round(max(0.0, float(t.get("vehicle_speed", 0)) * 0.9), 1)

        if not battery_fault:
            t["battery_voltage"] = round(self._clamp(t.get("battery_voltage", 12.4), 12.2, 12.6, 0.02), 2)
            t["battery_current"] = round(self._clamp(t.get("battery_current", 4.2), 3.5, 5.5, 0.08), 2)
            t["battery_soc"] = round(self._clamp(t.get("battery_soc", 78), 72, 92, 0.06), 1)
            t["battery_power"] = round(t["battery_voltage"] * t["battery_current"], 1)
            t["estimated_range"] = round(float(t["battery_soc"]) * 2.4, 1)

        if not climate_fault:
            t["cabin_temp"] = round(self._clamp(t.get("cabin_temp", 22.5), 21.5, 23.5, 0.05), 1)

        if ecus.get("brake", {}).get("status") == "HEALTHY":
            t["brake_status"] = "RELEASED"
        if ecus.get("steering", {}).get("status") == "HEALTHY":
            t["steering_status"] = "CENTERED"
        if ecus.get("adas", {}).get("status") == "HEALTHY":
            t["adas_status"] = "STANDBY"
        t["vehicle_state"] = "RUNNING" if t.get("vehicle_speed", 0) > 1 else "IDLE"

    def _clamp(self, value: float, lo: float, hi: float, step: float) -> float:
        value = float(value) + self._rng.uniform(-step, step)
        return max(lo, min(hi, value))

    def _make_frame(self, ecu_id: str, ecu_name: str, telemetry: dict, fault: bool) -> CANFrame:
        ids = {"engine": "0x101", "battery": "0x102", "brake": "0x103", "steering": "0x104", "climate": "0x105", "adas": "0x106"}
        msgs = {"engine": "MotorStatus", "battery": "BatteryStatus", "brake": "BrakeStatus", "steering": "SteeringStatus", "climate": "ClimateStatus", "adas": "ADASStatus"}
        payloads = {
            "engine": f"RPM={int(telemetry.get('vehicle_speed', 0) * 38)}",
            "battery": f"V={telemetry.get('battery_voltage', 0)}",
            "brake": f"ST={telemetry.get('brake_status', '—')}",
            "steering": f"ST={telemetry.get('steering_status', '—')}",
            "climate": f"T={telemetry.get('cabin_temp', 0)}",
            "adas": f"ST={telemetry.get('adas_status', '—')}",
        }
        data = payloads.get(ecu_id, "—")
        if fault:
            data = "ERR " + data
        return CANFrame(
            timestamp=utc_now_iso(),
            can_id=ids.get(ecu_id, "0x1FF"),
            message=msgs.get(ecu_id, "Unknown"),
            ecu=ecu_name,
            direction="TX",
            status="ERROR" if fault else "OK",
            data=data,
        )

    # ------------------------------------------------------------ fault --

    def inject_fault(self, ecu_id: str) -> dict[str, Any]:
        spec = FAULT_CATALOG.get(ecu_id)
        if not spec:
            return {"ok": False, "error": "unknown_ecu"}

        if spec["telemetry"]:
            self.state.update_telemetry(spec["telemetry"], source="simulation")
        health = 25 if spec["severity"] == "CRITICAL" else 45
        self.state.update_ecu(ecu_id, status="FAULT", health=health, fault_id=spec["fault_id"], recovery_state="AVAILABLE", last_event=spec["fault_id"])

        if ecu_id == "communication":
            self.state.add_can_frame(self._make_frame("communication", "CAN Bus", {}, True), error=True)

        record = DiagnosticRecord(
            dtc_id=new_id(), ecu=ecu_id, fault_id=spec["fault_id"], severity=spec["severity"],
            status="ACTIVE", detected_at=utc_now_iso(),
        )
        self.state.add_diagnostic(record)
        self.events.publish(VehicleEvent.create(
            "FAULT_DETECTED", source="simulation", ecu=ecu_id, severity=spec["severity"],
            payload={"fault_id": spec["fault_id"]},
        ))
        return {"ok": True, "fault_id": spec["fault_id"]}

    def start_recovery(self, ecu_id: str) -> dict[str, Any]:
        if self._recovery_active:
            return {"ok": False, "error": "recovery_in_progress"}
        snap = self.state.snapshot()
        ecu = snap["ecus"].get(ecu_id)
        if not ecu or not ecu.get("fault_id"):
            return {"ok": False, "error": "ecu_not_faulted"}
        self._recovery_active = True
        self._recovery_elapsed = 0.0
        self._recovery_ecu = ecu_id
        from sdv_console.core.models import RecoverySession
        self.state.set_recovery(RecoverySession(ecu=ecu_id, fault_id=ecu["fault_id"], status="ACTIVE", started_at=utc_now_iso()))
        self.state.update_ecu(ecu_id, status="RECOVERING", recovery_state="IN_PROGRESS", last_event="Recovery started")
        self.events.publish(VehicleEvent.create("RECOVERY_STARTED", source="simulation", ecu=ecu_id))
        return {"ok": True, "ecu": ecu_id}

    def _tick_recovery(self, dt: float) -> None:
        if not self._recovery_active or not self._recovery_ecu:
            return
        self._recovery_elapsed += dt
        if self._recovery_elapsed < RECOVERY_DURATION_S:
            return
        ecu_id = self._recovery_ecu
        self.state.update_ecu(ecu_id, status="HEALTHY", health=100, fault_id=None, recovery_state="IDLE", last_event="Recovered")
        self.state.clear_diagnostic(ecu_id)
        self.state.clear_can_error()
        from sdv_console.core.models import RecoverySession
        self.state.set_recovery(RecoverySession(ecu=ecu_id, fault_id="", status="SUCCESS", finished_at=utc_now_iso()))
        self.events.publish(VehicleEvent.create("RECOVERY_COMPLETED", source="simulation", ecu=ecu_id, severity="INFO"))
        self._recovery_active = False
        self._recovery_ecu = None
