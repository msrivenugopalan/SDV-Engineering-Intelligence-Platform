"""Autonomous Recovery Intelligence — deterministic policy, not an ML model.

Fault → Fault Manager → recovery policy → restart ECU task → health check → result.
"""

from __future__ import annotations

from sdv_console.config import FAULT_CATALOG, NOMINAL_TELEMETRY
from sdv_console.core.event_manager import EventManager
from sdv_console.core.events import (
    ECU_RECOVERY_FAILED,
    ECU_RECOVERY_STARTED,
    ECU_RECOVERY_SUCCESS,
    VehicleEvent,
    utc_now_iso,
)
from sdv_console.core.models import ARISession, RecoveryStep
from sdv_console.core.vehicle_state import VehicleStateManager

STEP_NAMES = [
    "FAULT DETECTED",
    "DIAGNOSTICS",
    "RECOVERY INITIATED",
    "ECU RESTART",
    "HEALTH CHECK",
    "RECOVERY SUCCESSFUL",
]


class ARIService:
    def __init__(self, state: VehicleStateManager, events: EventManager) -> None:
        self.state = state
        self.events = events
        self._elapsed = 0.0
        self._stage = -1
        self._correlation: str | None = None
        self._ecu: str | None = None
        self._fault_id: str | None = None

    def start(self, ecu_id: str, fault_id: str, correlation_id: str) -> None:
        self._elapsed = 0.0
        self._stage = 0
        self._ecu = ecu_id
        self._fault_id = fault_id
        self._correlation = correlation_id
        steps = [RecoveryStep(name=n, status="PENDING") for n in STEP_NAMES]
        steps[0].status = "DONE"
        steps[0].detail = f"{fault_id} on {ecu_id}"
        session = ARISession(
            ecu=ecu_id,
            fault_id=fault_id,
            correlation_id=correlation_id,
            started_at=utc_now_iso(),
            result="IN_PROGRESS",
            steps=steps,
        )
        self.state.set_ari(session)
        self.state.update_ecu(
            ecu_id,
            status="RECOVERING",
            recovery_state="IN_PROGRESS",
            task_state="RESTARTING",
            last_event="ARI recovery started",
        )
        self.state.update_diagnostic(ecu_id, recovery_status="IN_PROGRESS", diagnostic_status="RECOVERING")
        self.events.publish(
            VehicleEvent.create(
                ECU_RECOVERY_STARTED,
                source="ari",
                ecu=ecu_id,
                severity="INFO",
                payload={"fault_id": fault_id},
                correlation_id=correlation_id,
            )
        )

    def tick(self, dt: float) -> None:
        if self._stage < 0 or self._ecu is None:
            return
        self._elapsed += dt
        # ~1.2 s per remaining stage so a viva demo finishes in a few seconds.
        next_at = self._stage * 1.2
        if self._elapsed < next_at + 1.2:
            if self._stage == 0 and self._elapsed >= 0.3:
                self._advance(1, "Rule-based diagnostic record published")
            elif self._stage == 1 and self._elapsed >= 1.5:
                self._advance(2, "Recovery policy: restart affected FreeRTOS task")
            elif self._stage == 2 and self._elapsed >= 2.7:
                self._advance(3, f"Reinitialize {self._ecu} task")
                self.state.update_ecu(self._ecu, task_state="RESTARTING")
            elif self._stage == 3 and self._elapsed >= 3.9:
                self._advance(4, "Health check against nominal telemetry")
            elif self._stage == 4 and self._elapsed >= 5.1:
                self._complete_success()
        self._publish_session()

    def _advance(self, stage: int, detail: str) -> None:
        session = self.state.get_ari()
        for index, step in enumerate(session.steps):
            if index < stage:
                step.status = "DONE"
            elif index == stage:
                step.status = "ACTIVE"
                step.detail = detail
        self._stage = stage
        self.state.set_ari(session)

    def _complete_success(self) -> None:
        if self._ecu is None or self._correlation is None:
            return
        session = self.state.get_ari()
        for step in session.steps:
            step.status = "DONE"
        session.steps[-1].status = "DONE"
        session.steps[-1].detail = "ECU health restored"
        session.result = "SUCCESS"
        self.state.set_ari(session)

        restore = dict(NOMINAL_TELEMETRY)
        if self._ecu in FAULT_CATALOG:
            # Restore only the channels this ECU owns; leave others as they are.
            spec_keys = FAULT_CATALOG[self._ecu].get("telemetry", {})
            patch = {k: restore[k] for k in spec_keys if k in restore}
            if self._ecu == "battery":
                patch = {
                    "battery_voltage": restore["battery_voltage"],
                    "battery_current": restore["battery_current"],
                    "battery_power": restore["battery_power"],
                }
            if patch:
                self.state.update_telemetry(patch, source="ari")

        if self._ecu == "communication":
            self.state.set_can_bus_state("OK")

        self.state.update_ecu(
            self._ecu,
            status="HEALTHY",
            health=100,
            fault_id=None,
            recovery_state="SUCCESS",
            task_state="RUNNING",
            last_event="ARI recovery successful",
        )
        self.state.update_diagnostic(
            self._ecu,
            diagnostic_status="CLEARED",
            recovery_status="SUCCESS",
        )
        self.events.publish(
            VehicleEvent.create(
                ECU_RECOVERY_SUCCESS,
                source="ari",
                ecu=self._ecu,
                severity="INFO",
                payload={"fault_id": self._fault_id},
                correlation_id=self._correlation,
            )
        )
        self._stage = -1
        self._ecu = None

    def fail(self, reason: str) -> None:
        session = self.state.get_ari()
        session.result = "FAILED"
        if session.steps:
            session.steps[-1].status = "FAILED"
            session.steps[-1].detail = reason
        self.state.set_ari(session)
        if self._ecu:
            self.state.update_ecu(self._ecu, recovery_state="FAILED", status="FAULT")
            self.events.publish(
                VehicleEvent.create(
                    ECU_RECOVERY_FAILED,
                    source="ari",
                    ecu=self._ecu,
                    severity="HIGH",
                    payload={"reason": reason},
                    correlation_id=self._correlation or "",
                )
            )
        self._stage = -1

    def _publish_session(self) -> None:
        return

    @property
    def busy(self) -> bool:
        return self._stage >= 0
