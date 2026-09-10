"""MQTT bridge — optional. Stays idle (and the console stays fully usable)
if paho-mqtt isn't installed or MQTT_HOST isn't configured in config.py.
"""

from __future__ import annotations

import json
from typing import Any, Callable

from sdv_console.config import MQTT_HOST, MQTT_PORT, MQTT_TOPIC_EVENTS, MQTT_TOPIC_TELEMETRY
from sdv_console.core.event_bus import EventBus
from sdv_console.core.models import VehicleEvent
from sdv_console.core.vehicle_state import VehicleState


class MQTTBridge:
    def __init__(self, state: VehicleState, events: EventBus) -> None:
        self.state = state
        self.events = events
        self.connected = False
        self._client = None
        self.on_hardware_message: Callable[[dict[str, Any]], None] | None = None

    def start(self) -> None:
        if not MQTT_HOST:
            return
        try:
            import paho.mqtt.client as mqtt
        except ImportError:
            self.events.publish(VehicleEvent.create(
                "SYSTEM_LOG", source="mqtt", severity="WARNING",
                payload={"message": "paho-mqtt not installed; MQTT stays disconnected."},
            ))
            return
        self._client = mqtt.Client()
        self._client.on_connect = self._on_connect
        self._client.on_message = self._on_message
        try:
            self._client.connect(MQTT_HOST, MQTT_PORT, keepalive=30)
            self._client.loop_start()
        except Exception:
            self.state.set_service(mqtt=False)

    def stop(self) -> None:
        if self._client:
            self._client.loop_stop()
            self._client.disconnect()
        self.connected = False
        self.state.set_service(mqtt=False)

    def _on_connect(self, client, userdata, flags, rc) -> None:  # noqa: ANN001
        self.connected = rc == 0
        self.state.set_service(mqtt=self.connected)
        if self.connected:
            client.subscribe(MQTT_TOPIC_TELEMETRY)
            client.subscribe(MQTT_TOPIC_EVENTS)

    def _on_message(self, client, userdata, message) -> None:  # noqa: ANN001
        try:
            payload = json.loads(message.payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return
        if self.on_hardware_message is not None and isinstance(payload, dict):
            self.on_hardware_message(payload)
