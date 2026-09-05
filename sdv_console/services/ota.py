"""OTA workflow state machine — demonstration of steps, not a secure bootloader."""

from __future__ import annotations

from sdv_console.core.event_manager import EventManager
from sdv_console.core.events import OTA_COMPLETED, OTA_STARTED, VehicleEvent, utc_now_iso
from sdv_console.core.models import OTASession
from sdv_console.core.vehicle_state import VehicleStateManager
from sdv_console.services.history import HistoryService


class OTAService:
    def __init__(self, state: VehicleStateManager, events: EventManager, history: HistoryService) -> None:
        self.state = state
        self.events = events
        self.history = history
        self._elapsed = 0.0
        self._active = False
        self._from = "v1.0"
        self._to = "v1.1"
        self._ecu = "Battery ECU"

    def start(self, target_ecu: str, target_version: str) -> dict:
        current = self.state.snapshot()["firmware"]
        if self._active:
            return {"ok": False, "error": "ota_in_progress"}
        self._active = True
        self._elapsed = 0.0
        self._from = current
        self._to = target_version
        self._ecu = target_ecu
        session = OTASession(
            current_version=current,
            target_version=target_version,
            target_ecu=target_ecu,
            status="VALIDATING",
            progress=4,
            started_at=utc_now_iso(),
            checks={
                "firmware_validation": False,
                "integrity_check": False,
                "compatibility_check": False,
            },
            stages={
                "esp32_gateway": "PENDING",
                "stm32_transfer": "PENDING",
                "ecu_update": "PENDING",
                "verification": "PENDING",
            },
        )
        self.state.set_ota(session)
        self.events.publish(
            VehicleEvent.create(
                OTA_STARTED,
                source="ota",
                ecu=target_ecu,
                payload={"from": current, "to": target_version},
            )
        )
        return {"ok": True, "from": current, "to": target_version}

    def tick(self, dt: float) -> None:
        if not self._active:
            return
        self._elapsed += dt
        session = self.state.get_ota()
        t = self._elapsed

        if t >= 0.4:
            session.checks["firmware_validation"] = True
            session.status = "INTEGRITY"
            session.progress = max(session.progress, 12)
        if t >= 1.0:
            session.checks["integrity_check"] = True
            session.status = "COMPATIBILITY"
            session.progress = max(session.progress, 22)
        if t >= 1.6:
            session.checks["compatibility_check"] = True
            session.status = "DEPLOYING"
            session.progress = max(session.progress, 30)
        if t >= 2.2:
            session.stages["esp32_gateway"] = "DONE"
            session.progress = max(session.progress, 45)
        if t >= 3.4:
            session.stages["stm32_transfer"] = "DONE"
            session.progress = max(session.progress, 62)
        if t >= 4.6:
            session.stages["ecu_update"] = "DONE"
            session.progress = max(session.progress, 80)
        if t >= 5.6:
            session.stages["verification"] = "DONE"
            session.progress = 100
            session.status = "SUCCESS"
            session.result = "UPDATE SUCCESSFUL"
            session.finished_at = utc_now_iso()
            session.current_version = self._to
            self.state.set_ota(session)
            self.state.set_firmware(self._to, source="ota")
            self.history.insert_ota(self._ecu, self._from, self._to, "SUCCESS")
            self.events.publish(
                VehicleEvent.create(
                    OTA_COMPLETED,
                    source="ota",
                    ecu=self._ecu,
                    payload={"from": self._from, "to": self._to},
                )
            )
            self._active = False
            return

        # Smooth progress during transfer window.
        if 2.2 <= t < 5.6:
            session.progress = min(99, 30 + int((t - 1.6) / 4.0 * 70))
        self.state.set_ota(session)

    @property
    def busy(self) -> bool:
        return self._active
