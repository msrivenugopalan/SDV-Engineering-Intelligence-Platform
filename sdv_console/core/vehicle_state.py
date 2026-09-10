"""Central State — the single source of truth (see architecture doc, §3).

Every module (Digital Twin, Diagnostics, Telemetry, ARI, Voice, OTA Manager,
CAN Monitor...) reads from `snapshot()` and nothing else. Nothing computes
its own parallel copy of vehicle data. Mutations always go through a method
here, always publish an event, and always mark the snapshot cache dirty.

Perf note: `snapshot()` is called by several UI components (header, status
bar, the active view) within the same 250ms tick. Rebuilding the full dict
is the most expensive thing this app does, so it's cached and only rebuilt
when something actually changed since the last build.
"""

from __future__ import annotations

from collections import deque
from copy import deepcopy
from threading import Lock
from typing import Any

from sdv_console.config import ECU_CATALOG, TELEMETRY_HISTORY_POINTS
from sdv_console.core.event_bus import EventBus
from sdv_console.core.models import (
    CANFrame,
    DiagnosticRecord,
    ECUState,
    OTASession,
    RecoverySession,
    VehicleEvent,
    utc_now_iso,
)

NOMINAL_TELEMETRY = {
    "vehicle_speed": 0.0,
    "battery_soc": 82.0,
    "battery_voltage": 12.4,
    "battery_current": 4.2,
    "battery_power": 52.0,
    "estimated_range": 196.8,
    "engine_temp": 86.0,
    "cabin_temp": 22.5,
    "brake_status": "RELEASED",
    "steering_status": "CENTERED",
    "adas_status": "STANDBY",
    "vehicle_state": "IDLE",
}

HISTORY_KEYS = ("engine_temp", "battery_voltage", "battery_current", "battery_power", "battery_soc", "vehicle_speed", "cabin_temp")

RECENT_EVENTS_MAX = 300
CAN_FRAME_BUFFER = 200


class VehicleState:
    def __init__(self, events: EventBus) -> None:
        self.events = events
        self._lock = Lock()

        self._mode = "DISCONNECTED"       # DISCONNECTED | SIMULATION | HARDWARE
        self._connection_label = "Disconnected"
        self._paused = False
        self._firmware = "v1.0.0"
        self._uptime_started = utc_now_iso()

        self._ecus: dict[str, ECUState] = {
            e["id"]: ECUState(id=e["id"], name=e["name"], task=e["task"]) for e in ECU_CATALOG
        }
        self._telemetry: dict[str, Any] = dict(NOMINAL_TELEMETRY)
        self._history: dict[str, deque[float]] = {k: deque(maxlen=TELEMETRY_HISTORY_POINTS) for k in HISTORY_KEYS}

        self._can_frames: deque[CANFrame] = deque(maxlen=CAN_FRAME_BUFFER)
        self._can_bus_state = "IDLE"
        self._can_message_count = 0
        self._can_error_count = 0
        self._can_rate = 0.0
        self._can_rate_acc = 0.0
        self._can_count_prev = 0

        self._diagnostics: list[DiagnosticRecord] = []
        self._ota = OTASession(current_version=self._firmware, target_version=self._firmware, target_ecu="")
        self._recovery = RecoverySession(ecu="", fault_id="")
        self._ari_log: list[str] = []
        self._voice_log: list[dict[str, str]] = []
        self._recent_events: deque[dict[str, Any]] = deque(maxlen=RECENT_EVENTS_MAX)

        self._services = {"rest": False, "mqtt": False, "sqlite": False, "stm32": False, "esp32": False}

        self._dirty = True
        self._cache: dict[str, Any] | None = None

    # ---------------------------------------------------------- mutation --

    def _touch(self) -> None:
        self._dirty = True

    def _publish(self, event: VehicleEvent) -> None:
        self._recent_events.appendleft(event.to_dict())
        self.events.publish(event)

    def set_mode(self, mode: str, label: str, source: str = "console") -> None:
        with self._lock:
            self._mode = mode
            self._connection_label = label
            self._touch()
        self._publish(VehicleEvent.create("MODE_CHANGED", source=source, payload={"mode": mode}))

    def set_paused(self, paused: bool) -> None:
        with self._lock:
            self._paused = paused
            self._touch()

    def set_service(self, **flags: bool) -> None:
        with self._lock:
            self._services.update(flags)
            self._touch()

    def update_telemetry(self, values: dict[str, Any], source: str = "simulation") -> None:
        with self._lock:
            self._telemetry.update(values)
            for key in self._history:
                v = self._telemetry.get(key)
                if isinstance(v, (int, float)):
                    self._history[key].append(float(v))
            self._touch()

    def update_ecu(self, ecu_id: str, **fields: Any) -> None:
        with self._lock:
            ecu = self._ecus.get(ecu_id)
            if not ecu:
                return
            for k, v in fields.items():
                if hasattr(ecu, k):
                    setattr(ecu, k, v)
            ecu.last_update = utc_now_iso()
            self._touch()

    def restore_all_ecus(self, source: str = "simulation") -> None:
        with self._lock:
            for ecu in self._ecus.values():
                ecu.status = "HEALTHY"
                ecu.health = 100
                ecu.fault_id = None
                ecu.recovery_state = "IDLE"
                ecu.last_event = "Nominal"
                ecu.last_update = utc_now_iso()
            self._telemetry.update(NOMINAL_TELEMETRY)
            self._can_bus_state = "ACTIVE"
            self._can_error_count = 0
            self._touch()
        self._publish(VehicleEvent.create("FLEET_RESTORED", source=source))

    def disconnect_all_ecus(self) -> None:
        with self._lock:
            for ecu in self._ecus.values():
                ecu.status = "OFFLINE"
                ecu.health = 0
            self._can_bus_state = "IDLE"
            self._touch()

    def add_can_frame(self, frame: CANFrame, error: bool = False) -> None:
        with self._lock:
            self._can_frames.append(frame)
            self._can_message_count += 1
            if error:
                self._can_error_count += 1
                self._can_bus_state = "ERROR"
            elif self._can_bus_state != "ERROR":
                self._can_bus_state = "ACTIVE"
            self._touch()

    def clear_can_error(self) -> None:
        with self._lock:
            self._can_bus_state = "ACTIVE"
            self._touch()

    def tick_can_rate(self, dt: float) -> None:
        with self._lock:
            self._can_rate_acc += dt
            if self._can_rate_acc >= 1.0:
                delta = self._can_message_count - self._can_count_prev
                self._can_rate = delta / self._can_rate_acc
                self._can_count_prev = self._can_message_count
                self._can_rate_acc = 0.0
                self._touch()

    def add_diagnostic(self, record: DiagnosticRecord) -> None:
        with self._lock:
            self._diagnostics = [d for d in self._diagnostics if not (d.ecu == record.ecu and d.status == "ACTIVE")]
            self._diagnostics.insert(0, record)
            self._touch()

    def clear_diagnostic(self, ecu: str) -> None:
        with self._lock:
            for d in self._diagnostics:
                if d.ecu == ecu and d.status == "ACTIVE":
                    d.status = "CLEARED"
                    d.cleared_at = utc_now_iso()
            self._touch()

    def set_ota(self, session: OTASession) -> None:
        with self._lock:
            self._ota = session
            self._touch()

    def get_ota(self) -> OTASession:
        with self._lock:
            return deepcopy(self._ota)

    def set_firmware(self, version: str) -> None:
        with self._lock:
            self._firmware = version
            self._touch()

    def set_recovery(self, session: RecoverySession) -> None:
        with self._lock:
            self._recovery = session
            self._touch()

    def get_recovery(self) -> RecoverySession:
        with self._lock:
            return deepcopy(self._recovery)

    def push_ari_insight(self, text: str) -> None:
        with self._lock:
            self._ari_log.insert(0, text)
            self._ari_log = self._ari_log[:30]
            self._touch()

    def push_voice_log(self, utterance: str, reply: str) -> None:
        with self._lock:
            self._voice_log.insert(0, {"utterance": utterance, "reply": reply, "timestamp": utc_now_iso()})
            self._voice_log = self._voice_log[:30]
            self._touch()

    # -------------------------------------------------------------- read --

    @property
    def mode(self) -> str:
        with self._lock:
            return self._mode

    @property
    def paused(self) -> bool:
        with self._lock:
            return self._paused

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            if not self._dirty and self._cache is not None:
                return self._cache

            active_faults = [
                {"ecu": e.id, "name": e.name, "fault_id": e.fault_id, "status": e.status}
                for e in self._ecus.values() if e.status in {"FAULT", "RECOVERING"}
            ]
            snap = {
                "mode": self._mode,
                "connection_label": self._connection_label,
                "paused": self._paused,
                "firmware": self._firmware,
                "uptime_started": self._uptime_started,
                "ecus": {k: v.to_dict() for k, v in self._ecus.items()},
                "overall_health": self._overall_health(),
                "active_faults": active_faults,
                "telemetry": dict(self._telemetry),
                "telemetry_history": {k: list(v) for k, v in self._history.items()},
                "can": {
                    "bus_state": self._can_bus_state,
                    "message_count": self._can_message_count,
                    "error_count": self._can_error_count,
                    "messages_per_sec": round(self._can_rate, 1),
                    "bus_load_pct": min(100.0, round(self._can_rate / 3.0, 1)),
                },
                "can_frames": [f.to_dict() for f in self._can_frames],
                "diagnostics": [d.to_dict() for d in self._diagnostics],
                "ota": self._ota.to_dict(),
                "recovery": self._recovery.to_dict(),
                "ari_log": list(self._ari_log),
                "voice_log": list(self._voice_log),
                "recent_events": list(self._recent_events),
                "services": dict(self._services),
            }
            self._cache = snap
            self._dirty = False
            return snap

    def _overall_health(self) -> str:
        statuses = [e.status for e in self._ecus.values()]
        if any(s == "FAULT" for s in statuses):
            return "FAULT"
        if any(s in {"WARNING", "RECOVERING"} for s in statuses):
            return "WARNING"
        if all(s == "HEALTHY" for s in statuses):
            return "HEALTHY"
        return "OFFLINE"
