"""Vehicle State Manager — single source of truth for the engineering console.

SimulationAdapter and HardwareAdapter both write through this class.
UI views only read snapshots; they never own a second copy of ECU health.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from copy import deepcopy
from threading import RLock
from typing import Any

from sdv_console.config import (
    CAN_BUFFER_SIZE,
    ECU_CATALOG,
    NOMINAL_TELEMETRY,
    TELEMETRY_HISTORY_POINTS,
    VEHICLE_NAME,
)
from sdv_console.core.event_manager import EventManager
from sdv_console.core.events import (
    ECU_STATE_CHANGED,
    MODE_CHANGED,
    VehicleEvent,
    utc_now_iso,
)
from sdv_console.core.models import (
    ARISession,
    CANBusStatus,
    CANFrame,
    DiagnosticRecord,
    ECUState,
    OTASession,
)

Listener = Callable[[], None]


class VehicleStateManager:
    def __init__(self, events: EventManager) -> None:
        self._lock = RLock()
        self.events = events
        self._listeners: list[Listener] = []
        self._mode = "SIMULATION"  # SIMULATION | HARDWARE | DISCONNECTED
        self._firmware = "v1.0"
        self._vehicle_name = VEHICLE_NAME
        self._overall = "HEALTHY"
        self._ecus: dict[str, ECUState] = {}
        self._telemetry: dict[str, Any] = dict(NOMINAL_TELEMETRY)
        self._telemetry["ecu_heartbeat"] = {item["id"]: 0 for item in ECU_CATALOG}
        self._telemetry["can_message_count"] = 0
        self._history: dict[str, deque[float]] = {
            "engine_temp": deque(maxlen=TELEMETRY_HISTORY_POINTS),
            "battery_voltage": deque(maxlen=TELEMETRY_HISTORY_POINTS),
            "battery_current": deque(maxlen=TELEMETRY_HISTORY_POINTS),
            "battery_power": deque(maxlen=TELEMETRY_HISTORY_POINTS),
            "cabin_temp": deque(maxlen=TELEMETRY_HISTORY_POINTS),
        }
        self._diagnostics: list[DiagnosticRecord] = []
        self._ari = ARISession(
            ecu="",
            fault_id="",
            correlation_id="",
            started_at="",
            result="IDLE",
            steps=[],
        )
        self._ota = OTASession(
            current_version="v1.0",
            target_version="v1.1",
            target_ecu="Battery ECU",
            status="IDLE",
            progress=0,
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
        self._can_frames: deque[CANFrame] = deque(maxlen=CAN_BUFFER_SIZE)
        self._can = CANBusStatus(
            bus_state="OK",
            message_count=0,
            error_count=0,
            last_message="—",
        )
        self._mqtt_connected = False
        self._rest_running = False
        self._sqlite_ready = False
        self._hardware_stm32 = False
        self._hardware_esp32 = False
        self._paused = False
        self._init_ecus()

    def _init_ecus(self) -> None:
        now = utc_now_iso()
        for item in ECU_CATALOG:
            self._ecus[item["id"]] = ECUState(
                id=item["id"],
                name=item["name"],
                task_name=item["task_name"],
                responsibility=item["responsibility"],
                status="HEALTHY",
                health=100,
                last_update=now,
                fault_id=None,
                recovery_state="IDLE",
                task_state="RUNNING",
                last_event="Task started (simulation)",
                can_id=item["can_id"],
                message_name=item["message_name"],
                telemetry={},
            )

    def add_listener(self, callback: Listener) -> None:
        with self._lock:
            self._listeners.append(callback)

    def _notify(self) -> None:
        with self._lock:
            listeners = list(self._listeners)
        for callback in listeners:
            callback()

    def snapshot(self) -> dict[str, Any]:
        """Immutable-enough dict for UI and REST. Always copy before exposing."""
        with self._lock:
            return {
                "mode": self._mode,
                "paused": self._paused,
                "vehicle_name": self._vehicle_name,
                "firmware": self._firmware,
                "overall_health": self._overall,
                "connection_label": self.connection_label,
                "ecus": {k: v.to_dict() for k, v in self._ecus.items()},
                "telemetry": deepcopy(self._telemetry),
                "telemetry_history": {k: list(v) for k, v in self._history.items()},
                "diagnostics": [d.to_dict() for d in self._diagnostics],
                "active_faults": [
                    d.to_dict()
                    for d in self._diagnostics
                    if d.diagnostic_status in {"FAULT", "WARNING"}
                ],
                "ari": self._ari.to_dict(),
                "ota": self._ota.to_dict(),
                "can": self._can.to_dict(),
                "can_frames": [f.to_dict() for f in list(self._can_frames)[-80:]],
                "services": {
                    "stm32": self._hardware_stm32,
                    "esp32": self._hardware_esp32,
                    "mqtt": self._mqtt_connected,
                    "rest": self._rest_running,
                    "sqlite": self._sqlite_ready,
                },
            }

    @property
    def connection_label(self) -> str:
        if self._mode == "HARDWARE" and self._hardware_stm32:
            return "CONNECTED"
        if self._mode == "SIMULATION":
            return "SIMULATION MODE"
        return "DISCONNECTED"

    @property
    def mode(self) -> str:
        with self._lock:
            return self._mode

    def set_mode(self, mode: str, source: str = "console") -> None:
        with self._lock:
            if self._mode == mode:
                return
            self._mode = mode
        self.events.publish(
            VehicleEvent.create("MODE_CHANGED", source=source, payload={"mode": mode})
        )
        self._notify()

    def set_paused(self, paused: bool) -> None:
        with self._lock:
            self._paused = paused
        self._notify()

    def set_service_flags(self, **flags: bool) -> None:
        with self._lock:
            if "rest" in flags:
                self._rest_running = flags["rest"]
            if "sqlite" in flags:
                self._sqlite_ready = flags["sqlite"]
            if "mqtt" in flags:
                self._mqtt_connected = flags["mqtt"]
            if "stm32" in flags:
                self._hardware_stm32 = flags["stm32"]
            if "esp32" in flags:
                self._hardware_esp32 = flags["esp32"]
        self._notify()

    def set_firmware(self, version: str, source: str = "ota") -> None:
        with self._lock:
            self._firmware = version
            self._ota.current_version = version
        self._notify()

    def get_ecu(self, ecu_id: str) -> ECUState | None:
        with self._lock:
            ecu = self._ecus.get(ecu_id)
            return deepcopy(ecu) if ecu else None

    def update_ecu(self, ecu_id: str, **fields: Any) -> None:
        with self._lock:
            ecu = self._ecus.get(ecu_id)
            if ecu is None:
                return
            for key, value in fields.items():
                if hasattr(ecu, key):
                    setattr(ecu, key, value)
            ecu.last_update = utc_now_iso()
            self._recompute_overall()
        self.events.publish(
            VehicleEvent.create(
                ECU_STATE_CHANGED,
                source="state",
                ecu=ecu_id,
                payload=fields,
            )
        )
        self._notify()

    def update_telemetry(self, values: dict[str, Any], source: str = "simulation") -> None:
        with self._lock:
            self._telemetry.update(values)
            voltage = float(self._telemetry.get("battery_voltage", 0))
            current = float(self._telemetry.get("battery_current", 0))
            self._telemetry["battery_power"] = round(voltage * current, 2)
            for key in self._history:
                if key in self._telemetry and isinstance(self._telemetry[key], (int, float)):
                    self._history[key].append(float(self._telemetry[key]))
        self._notify()

    def bump_heartbeat(self, ecu_id: str) -> None:
        with self._lock:
            beats = self._telemetry.setdefault("ecu_heartbeat", {})
            beats[ecu_id] = int(beats.get(ecu_id, 0)) + 1

    def add_can_frame(self, frame: CANFrame, *, error: bool = False) -> None:
        with self._lock:
            self._can_frames.append(frame)
            self._can.message_count += 1
            self._telemetry["can_message_count"] = self._can.message_count
            self._can.last_message = f"{frame.can_id} {frame.message}"
            if error:
                self._can.error_count += 1
                self._can.bus_state = "ERROR"
            elif self._can.error_count == 0:
                self._can.bus_state = "OK"
        # CAN frames stay on the bus buffer; they are not Event Manager floods.

    def set_can_bus_state(self, bus_state: str, error: bool = False) -> None:
        with self._lock:
            self._can.bus_state = bus_state
            if error:
                self._can.error_count += 1
        self._notify()

    def add_diagnostic(self, record: DiagnosticRecord) -> None:
        with self._lock:
            self._diagnostics = [d for d in self._diagnostics if not (d.ecu == record.ecu and d.diagnostic_status in {"FAULT", "WARNING"})]
            self._diagnostics.insert(0, record)
        self._notify()

    def update_diagnostic(self, ecu: str, **fields: Any) -> None:
        with self._lock:
            for record in self._diagnostics:
                if record.ecu == ecu and record.diagnostic_status in {"FAULT", "WARNING", "RECOVERING"}:
                    for key, value in fields.items():
                        if hasattr(record, key):
                            setattr(record, key, value)
                    break
        self._notify()

    def set_ari(self, session: ARISession) -> None:
        with self._lock:
            self._ari = session
        self._notify()

    def get_ari(self) -> ARISession:
        with self._lock:
            return deepcopy(self._ari)

    def set_ota(self, session: OTASession) -> None:
        with self._lock:
            self._ota = session
            self._firmware = session.current_version
        self._notify()

    def get_ota(self) -> OTASession:
        with self._lock:
            return deepcopy(self._ota)

    def _recompute_overall(self) -> None:
        statuses = [e.status for e in self._ecus.values()]
        if any(s == "FAULT" for s in statuses):
            self._overall = "FAULT"
            self._telemetry["vehicle_state"] = "FAULTED"
        elif any(s == "RECOVERING" for s in statuses):
            self._overall = "RECOVERING"
            self._telemetry["vehicle_state"] = "RECOVERING"
        elif any(s == "WARNING" for s in statuses):
            self._overall = "WARNING"
            self._telemetry["vehicle_state"] = "DEGRADED"
        elif self._mode == "DISCONNECTED":
            self._overall = "OFFLINE"
            self._telemetry["vehicle_state"] = "OFFLINE"
        else:
            self._overall = "HEALTHY"
            self._telemetry["vehicle_state"] = "RUNNING"

    def mark_disconnected_ecus(self) -> None:
        with self._lock:
            for ecu in self._ecus.values():
                ecu.status = "OFFLINE"
                ecu.task_state = "SUSPENDED"
                ecu.health = 0
            self._recompute_overall()
        self._notify()

    def restore_healthy_ecus(self, source: str = "simulation") -> None:
        now = utc_now_iso()
        with self._lock:
            for ecu in self._ecus.values():
                ecu.status = "HEALTHY"
                ecu.health = 100
                ecu.fault_id = None
                ecu.recovery_state = "IDLE"
                ecu.task_state = "RUNNING"
                ecu.last_event = "Healthy"
                ecu.last_update = now
            self._telemetry.update(NOMINAL_TELEMETRY)
            self._can.bus_state = "OK"
            self._recompute_overall()
        self.events.publish(VehicleEvent.create(MODE_CHANGED, source=source, payload={"restored": True}))
        self._notify()
