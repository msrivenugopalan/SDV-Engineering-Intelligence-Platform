"""OTA workflow (architecture doc §13) — a demonstration state machine, not
a secure bootloader. Progresses on tick() so the UI can show it animate.
"""

from __future__ import annotations

from sdv_console.core.event_bus import EventBus
from sdv_console.core.models import OTASession, VehicleEvent, utc_now_iso
from sdv_console.core.vehicle_state import VehicleState
from sdv_console.services.history import HistoryService

STAGE_TIMINGS = (
    (0.5, "VALIDATING", {"firmware_validation": True}, 15),
    (1.2, "VALIDATING", {"integrity_check": True}, 30),
    (1.9, "VALIDATING", {"compatibility_check": True}, 42),
    (2.8, "DOWNLOADING", {}, 65),
    (4.2, "INSTALLING", {}, 88),
)
TOTAL_DURATION_S = 5.4


class OTAService:
    def __init__(self, state: VehicleState, events: EventBus, history: HistoryService) -> None:
        self.state = state
        self.events = events
        self.history = history
        self._active = False
        self._elapsed = 0.0
        self._from = "v1.0.0"
        self._to = "v2.0.0"
        self._ecu = ""

    @property
    def busy(self) -> bool:
        return self._active

    def start(self, target_ecu: str, target_version: str) -> dict:
        if self._active:
            return {"ok": False, "error": "ota_in_progress"}
        current = self.state.snapshot()["firmware"]
        self._active = True
        self._elapsed = 0.0
        self._from = current
        self._to = target_version
        self._ecu = target_ecu
        session = OTASession(
            current_version=current, target_version=target_version, target_ecu=target_ecu,
            status="VALIDATING", progress=4, checks={"firmware_validation": False, "integrity_check": False, "compatibility_check": False},
            started_at=utc_now_iso(), from_version=current,
        )
        self.state.set_ota(session)
        self.events.publish(VehicleEvent.create("OTA_STARTED", source="ota", ecu=target_ecu, payload={"from": current, "to": target_version}))
        return {"ok": True, "from": current, "to": target_version}

    def tick(self, dt: float) -> None:
        if not self._active:
            return
        self._elapsed += dt
        session = self.state.get_ota()

        for threshold, status, checks, progress in STAGE_TIMINGS:
            if self._elapsed >= threshold:
                session.status = status
                session.checks.update(checks)
                session.progress = max(session.progress, progress)

        if self._elapsed >= TOTAL_DURATION_S:
            session.status = "COMPLETED"
            session.progress = 100
            session.finished_at = utc_now_iso()
            self.state.set_ota(session)
            self.state.set_firmware(self._to)
            self.state.update_ecu(self._ecu_id(), firmware=self._to)
            self.history.insert_ota(self._ecu, self._from, self._to, "SUCCESS")
            self.events.publish(VehicleEvent.create("OTA_COMPLETED", source="ota", ecu=self._ecu, payload={"from": self._from, "to": self._to}))
            self._active = False
            return

        if 1.9 < self._elapsed < TOTAL_DURATION_S:
            session.progress = min(99, int(42 + (self._elapsed - 1.9) / (TOTAL_DURATION_S - 1.9) * 57))
        self.state.set_ota(session)

    def _ecu_id(self) -> str:
        # target_ecu is a display name ("Battery ECU"); map back to the id
        # vehicle_state indexes ECUs by.
        mapping = {"Motor ECU": "engine", "Battery ECU": "battery", "Brake ECU": "brake", "Steering ECU": "steering", "Climate ECU": "climate", "ADAS ECU": "adas"}
        return mapping.get(self._ecu, "battery")
