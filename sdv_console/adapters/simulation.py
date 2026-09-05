"""Simulation adapter — virtual ECUs, telemetry, CAN, faults.

All simulated activity enters VehicleStateManager and EventManager, the same
interfaces STM32/ESP32 will use later.
"""

from __future__ import annotations

import random
from typing import Any

from sdv_console.adapters.base import VehicleSource
from sdv_console.config import FAULT_CATALOG
from sdv_console.core.event_manager import EventManager
from sdv_console.core.events import CAN_ERROR, FAULT_EVENT_BY_ECU, SYSTEM_LOG, VehicleEvent
from sdv_console.core.vehicle_state import VehicleStateManager
from sdv_console.services.ari import ARIService
from sdv_console.services.can_bus import make_frame
from sdv_console.services.diagnostics import DiagnosticEngine
from sdv_console.services.ota import OTAService


class SimulationAdapter(VehicleSource):
    name = "simulation"

    def __init__(
        self,
        state: VehicleStateManager,
        events: EventManager,
        diagnostics: DiagnosticEngine,
        ari: ARIService,
        ota: OTAService,
    ) -> None:
        self.state = state
        self.events = events
        self.diagnostics = diagnostics
        self.ari = ari
        self.ota = ota
        self._running = False
        self._can_index = 0
        self._rng = random.Random(42)
        self._pending_ari: tuple[str, str, str, float] | None = None

    def start(self) -> None:
        self._running = True
        self.state.set_mode("SIMULATION", source="simulation")
        self.state.restore_healthy_ecus(source="simulation")
        self.events.publish(
            VehicleEvent.create(
                SYSTEM_LOG,
                source="simulation",
                payload={"message": "Simulation started. Data is generated in software, not from STM32 sensors."},
            )
        )

    def stop(self) -> None:
        self._running = False
        self.state.set_mode("DISCONNECTED", source="simulation")
        self.state.mark_disconnected_ecus()

    def tick(self, dt: float) -> None:
        if not self._running or self.state.snapshot()["paused"]:
            return
        snap = self.state.snapshot()
        telemetry = dict(snap["telemetry"])
        self._nudge_healthy(telemetry, snap["ecus"])
        self.state.update_telemetry(telemetry, source="simulation")

        for ecu_id, ecu in snap["ecus"].items():
            self.state.bump_heartbeat(ecu_id)
            fault = ecu["status"] in {"FAULT", "RECOVERING"}
            frame = make_frame(ecu_id, ecu["name"], telemetry, ecu["health"], fault)
            self.state.add_can_frame(frame, error=fault and ecu["status"] == "FAULT")

        if snap["can"]["bus_state"] == "ERROR":
            self._can_index += 1

        if self._pending_ari:
            ecu_id, fault_id, cid, acc = self._pending_ari
            acc += dt
            if acc >= 0.8 and not self.ari.busy:
                self.ari.start(ecu_id, fault_id, cid)
                self._pending_ari = None
            else:
                self._pending_ari = (ecu_id, fault_id, cid, acc)

        self.ari.tick(dt)
        self.ota.tick(dt)

    def _nudge_healthy(self, telemetry: dict[str, Any], ecus: dict) -> None:
        """Small noise around nominal values for healthy ECUs only."""
        battery_fault = ecus.get("battery", {}).get("status") in {"FAULT", "RECOVERING"}
        engine_fault = ecus.get("engine", {}).get("status") in {"FAULT", "RECOVERING"}
        climate_fault = ecus.get("climate", {}).get("status") in {"FAULT", "RECOVERING"}

        if not engine_fault:
            telemetry["engine_temp"] = round(self._clamp(telemetry.get("engine_temp", 86), 84, 92, 0.15), 1)
        if not battery_fault:
            telemetry["battery_voltage"] = round(self._clamp(telemetry.get("battery_voltage", 12.4), 12.2, 12.6, 0.02), 2)
            telemetry["battery_current"] = round(self._clamp(telemetry.get("battery_current", 4.2), 3.5, 5.5, 0.08), 2)
        if not climate_fault:
            telemetry["cabin_temp"] = round(self._clamp(telemetry.get("cabin_temp", 22.5), 21.5, 23.5, 0.05), 1)

        if ecus.get("brake", {}).get("status") == "HEALTHY":
            telemetry["brake_status"] = "RELEASED"
        if ecus.get("steering", {}).get("status") == "HEALTHY":
            telemetry["steering_status"] = "CENTERED"
        if ecus.get("adas", {}).get("status") == "HEALTHY":
            telemetry["adas_status"] = "STANDBY"

    def _clamp(self, value: float, lo: float, hi: float, step: float) -> float:
        value = float(value) + self._rng.uniform(-step, step)
        return max(lo, min(hi, value))

    def inject_fault(self, ecu_id: str, correlation_id: str | None = None) -> dict[str, Any]:
        if ecu_id not in FAULT_CATALOG:
            return {"ok": False, "error": "unknown_ecu"}
        spec = FAULT_CATALOG[ecu_id]
        event_type = FAULT_EVENT_BY_ECU[ecu_id]
        event = VehicleEvent.create(
            event_type,
            source="simulation",
            ecu=ecu_id,
            severity=spec["severity"],
            payload={"fault_id": spec["fault_id"]},
            correlation_id=correlation_id,
        )
        if spec["telemetry"]:
            self.state.update_telemetry(spec["telemetry"], source="simulation")

        health = 28 if spec["severity"] == "CRITICAL" else 40
        self.state.update_ecu(
            ecu_id,
            status="FAULT",
            health=health,
            fault_id=spec["fault_id"],
            recovery_state="AVAILABLE",
            task_state="FAULTED",
            last_event=spec["fault_id"],
        )
        if ecu_id == "communication":
            self.state.set_can_bus_state("ERROR", error=True)
            self.events.publish(
                VehicleEvent.create(CAN_ERROR, source="simulation", ecu="communication", severity="HIGH")
            )

        self.events.publish(event)
        record = self.diagnostics.evaluate_fault(ecu_id, source="simulation", correlation_id=event.correlation_id)
        self._pending_ari = (ecu_id, spec["fault_id"], event.correlation_id, 0.0)
        return {"ok": True, "fault_id": spec["fault_id"], "diagnostic": record.to_dict()}

    def start_recovery(self, ecu_id: str | None = None) -> dict[str, Any]:
        if self.ari.busy:
            return {"ok": False, "error": "recovery_in_progress"}
        snap = self.state.snapshot()
        if ecu_id is None:
            active = snap["active_faults"]
            if not active:
                return {"ok": False, "error": "no_active_fault"}
            ecu_id = active[0]["ecu"]
        ecu = snap["ecus"].get(ecu_id)
        if not ecu or not ecu.get("fault_id"):
            return {"ok": False, "error": "ecu_not_faulted"}
        self.ari.start(ecu_id, ecu["fault_id"], correlation_id="manual")
        return {"ok": True, "ecu": ecu_id}

    def start_ota(self, target_ecu: str, target_version: str) -> dict[str, Any]:
        return self.ota.start(target_ecu, target_version)
