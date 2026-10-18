"""EngineeringPlatform — the "APPLICATION / API LAYER" box in the
architecture doc. Every view/button calls a method here; nothing reaches
into VehicleState, an adapter, or a service directly. This is what keeps
"single source of truth" true in practice, not just on paper.
"""

from __future__ import annotations

from typing import Any

from sdv_console.adapters.hardware import HardwareAdapter
from sdv_console.adapters.simulation import SimulationAdapter
from sdv_console.core.event_bus import EventBus
from sdv_console.core.vehicle_state import VehicleState
from sdv_console.services.ari import ARIService
from sdv_console.services.history import HistoryService
from sdv_console.services.mqtt_bridge import MQTTBridge
from sdv_console.services.ota import OTAService
from sdv_console.services.voice import VoiceService
from sdv_console.services.serial_bridge import SerialBridge

class EngineeringPlatform:
    def __init__(self) -> None:
        self.events = EventBus()
        self.state = VehicleState(self.events)

        self.history = HistoryService(self.events)
        self.state.set_service(sqlite=self.history.ready)

        self.ari = ARIService(self.state, self.events)
        self.voice = VoiceService(self.state, self.ari, self.inject_fault, self.start_recovery)
        self.ota_service = OTAService(self.state, self.events, self.history)

        self.sim = SimulationAdapter(self.state, self.events)
        self.hardware = HardwareAdapter(self.state, self.events)

        self.mqtt = MQTTBridge(self.state, self.events)
        self.mqtt.on_hardware_message = (
            lambda message: self.hardware.ingest(
                message, transport="mqtt"
            )
        )
        self.serial_bridge = SerialBridge(
            on_telemetry=self._handle_serial_telemetry,
            port="COM9",
            baudrate=115200,
        )
    def _handle_serial_telemetry(self, message: dict[str, Any]) -> None:
      """Forward valid STM32 telemetry into the existing vehicle state."""
      self.hardware.ingest(message)

      if self.state.mode != "HARDWARE":
        result = self.set_mode("HARDWARE")
        if result.get("ok"):
            print("[SDV] STM32 telemetry received; HARDWARE mode activated.")
        else:
            print(f"[SDV] Could not activate HARDWARE mode: {result}")
    def start(self) -> None:
       self.sim.start()
       self.mqtt.start()
       self.serial_bridge.start()

    def shutdown(self) -> None:
      self.serial_bridge.stop()
      self.sim.stop()
      self.hardware.stop()
      self.mqtt.stop()
      self.history.close()

    def active_source(self):
        return self.hardware if self.state.mode == "HARDWARE" else self.sim

    def snapshot(self) -> dict[str, Any]:
        return self.state.snapshot()

    def tick(self, dt: float) -> None:
        source = self.active_source()
        source.tick(dt)
        if source is not self.hardware:
            self.hardware.tick(dt)  # keep watching for a stale link even in SIMULATION
        self.ota_service.tick(dt)

    # ------------------------------------------------------------ actions --

    
    def set_mode(self, mode: str) -> dict[str, Any]:
        if mode == "HARDWARE" and not self.hardware.connected:
            return {
                "ok": False,
                "error": "hardware_unavailable",
                "detail": (
                    "STM32/ESP32 are not linked yet. "
                    "Send data to POST /hardware/ingest first."
                ),
            }

        if mode == "SIMULATION":
            self.sim.start()
            self.state.set_mode(
                "SIMULATION", "Simulation", source="console"
            )
        elif mode == "DISCONNECTED":
            self.sim.stop()
            self.state.set_mode(
                "DISCONNECTED", "Disconnected", source="console"
            )
        elif mode == "HARDWARE":
            self.state.set_mode(
                "HARDWARE", "Hardware", source="console"
            )
        else:
            return {
                "ok": False,
                "error": "invalid_mode",
                "detail": f"Unsupported mode: {mode}",
            }

        return {"ok": True, "mode": self.state.mode}


    def inject_fault(self, ecu_id: str) -> dict[str, Any]:
        return self.active_source().inject_fault(ecu_id)

    def start_recovery(self, ecu_id: str) -> dict[str, Any]:
        return self.active_source().start_recovery(ecu_id)

    def start_ota(self, target_ecu: str, target_version: str, requested_by: str = "engineering-demo", role: str = "engineering", pin: str | None = None) -> dict[str, Any]:
        if self.ota_service.busy:
            return {"ok": False, "error": "ota_in_progress"}
        return self.ota_service.start(target_ecu, target_version, requested_by=requested_by, role=role, pin=pin)

    def handle_voice(self, utterance: str) -> str:
        reply = self.voice.handle(utterance)
        self.state.push_voice_log(utterance, reply)
        self.history.insert_voice(utterance, reply)
        return reply
