"""Engineering platform — wires state, events, adapters, and services.

The CustomTkinter UI and the REST API both call this object. Views never
talk to each other.
"""

from __future__ import annotations

from typing import Any

from sdv_console.adapters.hardware import HardwareAdapter
from sdv_console.adapters.simulation import SimulationAdapter
from sdv_console.config import ECU_CATALOG
from sdv_console.core.event_manager import EventManager
from sdv_console.core.events import SYSTEM_LOG, VOICE_COMMAND, VehicleEvent
from sdv_console.core.vehicle_state import VehicleStateManager
from sdv_console.services.ari import ARIService
from sdv_console.services.diagnostics import DiagnosticEngine
from sdv_console.services.history import HistoryService
from sdv_console.services.mqtt_bridge import MQTTBridge
from sdv_console.services.ota import OTAService
from sdv_console.services.voice import parse_command


class EngineeringPlatform:
    def __init__(self) -> None:
        self.events = EventManager()
        self.state = VehicleStateManager(self.events)
        self.history = HistoryService(self.events)
        self.diagnostics = DiagnosticEngine(self.state, self.events)
        self.ari = ARIService(self.state, self.events)
        self.ota = OTAService(self.state, self.events, self.history)
        self.sim = SimulationAdapter(self.state, self.events, self.diagnostics, self.ari, self.ota)
        self.hardware = HardwareAdapter(self.state, self.events)
        self.mqtt = MQTTBridge(self.state, self.events)
        self._pending_voice: dict[str, Any] | None = None
        self._telemetry_persist_acc = 0.0
        self.navigate = lambda page: None  # set by the Tk app
        self.speak = lambda text: None
        self.state.set_service_flags(sqlite=self.history.ready)

    def start(self) -> None:
        self.sim.start()
        self.hardware.start()
        self.mqtt.start()
        self.events.publish(
            VehicleEvent.create(
                SYSTEM_LOG,
                source="platform",
                payload={"message": "Engineering platform started in SIMULATION MODE."},
            )
        )

    def shutdown(self) -> None:
        self.mqtt.stop()
        self.sim.stop()
        self.hardware.stop()

    def tick(self, dt: float) -> None:
        source = self.active_source()
        source.tick(dt)
        self._telemetry_persist_acc += dt
        if self._telemetry_persist_acc >= 5.0:
            self._telemetry_persist_acc = 0.0
            self.history.insert_telemetry_sample(self.state.snapshot()["telemetry"])

    def active_source(self):
        if self.state.mode == "HARDWARE":
            return self.hardware
        return self.sim

    def snapshot(self) -> dict[str, Any]:
        return self.state.snapshot()

    def inject_fault(self, ecu_id: str) -> dict[str, Any]:
        return self.active_source().inject_fault(ecu_id)

    def start_recovery(self, ecu_id: str | None = None) -> dict[str, Any]:
        return self.active_source().start_recovery(ecu_id)

    def start_ota(self, target_ecu: str = "Battery ECU", target_version: str = "v1.1") -> dict[str, Any]:
        return self.active_source().start_ota(target_ecu, target_version)

    def set_mode(self, mode: str) -> dict[str, Any]:
        if mode == "HARDWARE" and not self.hardware.connected:
            return {
                "ok": False,
                "error": "hardware_unavailable",
                "detail": "STM32/ESP32 are not linked. Stay in SIMULATION MODE until UART/MQTT is connected.",
            }
        if mode == "SIMULATION":
            self.sim.start()
        elif mode == "DISCONNECTED":
            self.sim.stop()
        else:
            self.state.set_mode(mode, source="console")
        return {"ok": True, "mode": self.state.mode}

    def handle_voice(self, utterance: str, *, confirmed: bool = False) -> dict[str, Any]:
        parsed = parse_command(utterance)
        self.events.publish(
            VehicleEvent.create(
                VOICE_COMMAND,
                source="voice",
                payload={"utterance": utterance, "parsed": parsed},
            )
        )
        if not parsed.get("ok"):
            reply = parsed.get("detail", "Command not recognized.")
            self.history.insert_voice(utterance, str(parsed), "rejected")
            self.speak(reply)
            return {**parsed, "reply": reply}

        intent = parsed["intent"]
        if intent == "confirm":
            if not self._pending_voice:
                reply = "There is nothing waiting to confirm."
                self.speak(reply)
                return {"ok": True, "reply": reply}
            pending = self._pending_voice
            self._pending_voice = None
            return self._execute_intent(pending, utterance)

        if intent == "cancel":
            self._pending_voice = None
            reply = "Cancelled."
            self.speak(reply)
            return {"ok": True, "reply": reply}

        if parsed.get("destructive") and not confirmed:
            self._pending_voice = parsed
            prompt = parsed.get("confirm_prompt", "Confirm this operation?")
            self.speak(prompt)
            self.history.insert_voice(utterance, intent, "pending_confirm")
            return {"ok": True, "pending": True, "reply": prompt, "parsed": parsed}

        return self._execute_intent(parsed, utterance)

    def _execute_intent(self, parsed: dict[str, Any], utterance: str) -> dict[str, Any]:
        intent = parsed["intent"]
        snap = self.snapshot()
        reply = ""
        extra: dict[str, Any] = {}

        if intent == "inject_fault":
            extra = self.inject_fault(parsed["ecu"])
            reply = f"Injected {parsed['ecu']} fault." if extra.get("ok") else extra.get("error", "Failed.")
            self.navigate("Fault Injection")
        elif intent == "start_ota":
            extra = self.start_ota(parsed.get("target_ecu", "Battery ECU"), parsed.get("target_version", "v1.1"))
            reply = "OTA workflow started." if extra.get("ok") else extra.get("error", "OTA failed to start.")
            self.navigate("OTA Manager")
        elif intent == "start_recovery":
            extra = self.start_recovery()
            reply = "Recovery started." if extra.get("ok") else extra.get("error", "No recovery started.")
            self.navigate("Autonomous Recovery")
        elif intent == "show_vehicle_status":
            reply = (
                f"Vehicle is {snap['overall_health']} in {snap['connection_label']}. "
                f"Firmware {snap['firmware']}."
            )
            self.navigate("Vehicle Overview")
        elif intent == "show_faults":
            faults = snap["active_faults"]
            if not faults:
                reply = "There are no active faults."
            else:
                names = ", ".join(f"{f['fault_id']} on {f['ecu']}" for f in faults)
                reply = f"Active faults: {names}."
            self.navigate("Diagnostics")
        elif intent == "query_battery_voltage":
            v = snap["telemetry"].get("battery_voltage")
            bat = snap["ecus"]["battery"]
            reply = f"Battery voltage is {v} volts. Battery ECU is {bat['status']}."
            self.navigate("Live Telemetry")
        elif intent == "query_ecu":
            ecu_id = parsed.get("ecu", "battery")
            ecu = snap["ecus"].get(ecu_id)
            if not ecu:
                reply = "Unknown ECU."
            else:
                reply = (
                    f"{ecu['name']} is {ecu['status']}. Last event: {ecu['last_event']}. "
                    f"Recovery state: {ecu['recovery_state']}."
                )
                if ecu["status"] == "HEALTHY" and "success" in ecu["last_event"].lower():
                    reply = f"{ecu['name']} is healthy after successful recovery."
            self.navigate("Virtual ECUs")
        elif intent == "show_page":
            page = parsed.get("page", "Vehicle Overview")
            self.navigate(page)
            reply = f"Showing {page}."
        else:
            reply = "Command recognized but not implemented."

        self.speak(reply)
        self.history.insert_voice(utterance, intent, reply)
        return {"ok": True, "reply": reply, "intent": intent, **extra}

    def ecu_catalog(self) -> list[dict]:
        return list(ECU_CATALOG)
