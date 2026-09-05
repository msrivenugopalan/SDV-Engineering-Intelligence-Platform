"""Explainable diagnostic engine — threshold rules, not a trained ML model."""

from __future__ import annotations

from sdv_console.config import DIAGNOSTIC_THRESHOLDS, FAULT_CATALOG
from sdv_console.core.event_manager import EventManager
from sdv_console.core.events import DIAGNOSTIC_CREATED, VehicleEvent, utc_now_iso
from sdv_console.core.models import DiagnosticRecord
from sdv_console.core.vehicle_state import VehicleStateManager


class DiagnosticEngine:
    def __init__(self, state: VehicleStateManager, events: EventManager) -> None:
        self.state = state
        self.events = events

    def evaluate_fault(self, ecu_id: str, source: str, correlation_id: str) -> DiagnosticRecord:
        spec = FAULT_CATALOG[ecu_id]
        telemetry = self.state.snapshot()["telemetry"]
        confidence, evidence = self._confidence(ecu_id, telemetry)
        record = DiagnosticRecord(
            fault_id=spec["fault_id"],
            ecu=ecu_id,
            detected_time=utc_now_iso(),
            severity=spec["severity"],
            description=spec["description"],
            possible_cause=spec["possible_cause"],
            diagnostic_status="FAULT",
            recovery_status="AVAILABLE",
            confidence=confidence,
            recommended_action=f"Run ARI recovery for {spec['label']}.",
            evidence=evidence,
        )
        self.state.add_diagnostic(record)
        self.events.publish(
            VehicleEvent.create(
                DIAGNOSTIC_CREATED,
                source=source,
                ecu=ecu_id,
                severity=spec["severity"],
                payload=record.to_dict(),
                correlation_id=correlation_id,
            )
        )
        return record

    def _confidence(self, ecu_id: str, telemetry: dict) -> tuple[int, list[str]]:
        evidence: list[str] = []
        if ecu_id == "battery":
            voltage = float(telemetry.get("battery_voltage", 12.4))
            current = float(telemetry.get("battery_current", 0))
            low = DIAGNOSTIC_THRESHOLDS["battery_voltage_low"]
            crit = DIAGNOSTIC_THRESHOLDS["battery_voltage_critical"]
            evidence.append(f"Battery voltage {voltage:.2f} V (low < {low} V)")
            if current > 12:
                evidence.append(f"Battery current {current:.1f} A abnormal for idle load")
            if voltage < crit:
                return 96, evidence
            if voltage < low:
                return 88, evidence
            return 70, evidence
        if ecu_id == "engine":
            temp = float(telemetry.get("engine_temp", 86))
            evidence.append(f"Engine temperature {temp:.1f} C")
            if temp >= DIAGNOSTIC_THRESHOLDS["engine_temp_critical"]:
                return 94, evidence
            return 80, evidence
        spec = FAULT_CATALOG[ecu_id]
        evidence.append(spec["description"])
        return 85, evidence
