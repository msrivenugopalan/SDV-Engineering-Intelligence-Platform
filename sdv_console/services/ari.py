"""ARI — Autonomous Recovery Intelligence (architecture doc §14).

Deliberately rule-based, not a free-form LLM: every sentence it produces is
templated from a real field already sitting in Central State (fault_id,
ecu, severity, telemetry value). It should never say anything the state
doesn't already show — that's the "never invent vehicle conditions" rule
from the spec, and it's what makes the insight trustworthy for an engineer
reading it during a demo.
"""

from __future__ import annotations

from sdv_console.core.event_bus import EventBus
from sdv_console.core.models import VehicleEvent
from sdv_console.core.vehicle_state import VehicleState

ECU_LABELS = {
    "engine": "Motor ECU", "battery": "Battery ECU", "brake": "Brake ECU",
    "steering": "Steering ECU", "climate": "Climate ECU", "adas": "ADAS ECU",
    "communication": "Communication",
}


class ARIService:
    def __init__(self, state: VehicleState, events: EventBus) -> None:
        self.state = state
        events.subscribe("FAULT_DETECTED", self._on_fault)
        events.subscribe("RECOVERY_STARTED", self._on_recovery_started)
        events.subscribe("RECOVERY_COMPLETED", self._on_recovery_done)
        events.subscribe("OTA_COMPLETED", self._on_ota)
        events.subscribe("VEHICLE_CONNECTED", self._on_hw_connected)
        events.subscribe("VEHICLE_DISCONNECTED", self._on_hw_disconnected)

    def _on_fault(self, event: VehicleEvent) -> None:
        ecu = ECU_LABELS.get(event.ecu or "", event.ecu or "Unknown ECU")
        fault_id = (event.payload or {}).get("fault_id", "an unspecified fault")
        self.state.push_ari_insight(
            f"{ecu} reported {fault_id} (severity: {event.severity}). "
            f"A diagnostic record has been generated. Recovery is available from the Autonomous Recovery page."
        )

    def _on_recovery_started(self, event: VehicleEvent) -> None:
        ecu = ECU_LABELS.get(event.ecu or "", event.ecu or "Unknown ECU")
        self.state.push_ari_insight(f"Recovery sequence started for {ecu}. Monitoring ECU health for restoration.")

    def _on_recovery_done(self, event: VehicleEvent) -> None:
        ecu = ECU_LABELS.get(event.ecu or "", event.ecu or "Unknown ECU")
        self.state.push_ari_insight(f"{ecu} recovery completed successfully. Status restored to HEALTHY, diagnostic cleared.")

    def _on_ota(self, event: VehicleEvent) -> None:
        p = event.payload or {}
        self.state.push_ari_insight(
            f"OTA deployment to {event.ecu} completed: firmware updated from {p.get('from')} to {p.get('to')}."
        )

    def _on_hw_connected(self, event: VehicleEvent) -> None:
        self.state.push_ari_insight("STM32/ESP32 link established. Hardware telemetry is now available for HARDWARE MODE.")

    def _on_hw_disconnected(self, event: VehicleEvent) -> None:
        self.state.push_ari_insight("STM32/ESP32 link lost. Falling back to the last known state; reconnect to resume live hardware data.")

    def explain_current_state(self) -> str:
        """On-demand summary for the ARI Assistant page / voice 'show vehicle health'."""
        snap = self.state.snapshot()
        health = snap["overall_health"]
        faults = snap["active_faults"]
        lines = [f"Overall vehicle health is {health}."]
        if faults:
            for f in faults:
                lines.append(f"{ECU_LABELS.get(f['ecu'], f['ecu'])} is in {f['status']} state ({f.get('fault_id')}).")
        else:
            lines.append("No active faults across any of the 6 ECUs.")
        ota = snap["ota"]
        if ota.get("status") not in {"IDLE", "COMPLETED", None}:
            lines.append(f"An OTA deployment is in progress: {ota.get('status')} ({ota.get('progress')}%).")
        can = snap["can"]
        if can["bus_state"] == "ERROR":
            lines.append("CAN bus is reporting errors — check Communication ECU.")
        return " ".join(lines)
