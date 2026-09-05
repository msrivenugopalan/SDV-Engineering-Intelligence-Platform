"""MQTT bridge — ready to publish/subscribe; idle until a broker host is set."""

from __future__ import annotations

from sdv_console.config import MQTT_HOST, MQTT_PORT, MQTT_TOPIC_COMMANDS, MQTT_TOPIC_EVENTS
from sdv_console.core.event_manager import EventManager
from sdv_console.core.events import SYSTEM_LOG, VehicleEvent
from sdv_console.core.vehicle_state import VehicleStateManager


class MQTTBridge:
    def __init__(self, state: VehicleStateManager, events: EventManager) -> None:
        self.state = state
        self.events = events
        self.connected = False
        self._client = None

    def start(self) -> None:
        if not MQTT_HOST:
            self.events.publish(
                VehicleEvent.create(
                    SYSTEM_LOG,
                    source="mqtt",
                    payload={"message": "MQTT idle — set MQTT_HOST in config.py when a broker is available."},
                )
            )
            self.state.set_service_flags(mqtt=False)
            return
        try:
            import paho.mqtt.client as mqtt  # type: ignore
        except ImportError:
            self.events.publish(
                VehicleEvent.create(
                    SYSTEM_LOG,
                    source="mqtt",
                    payload={"message": "paho-mqtt not installed; MQTT remains disconnected."},
                )
            )
            return
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
        client.on_connect = self._on_connect
        client.on_message = self._on_message
        try:
            client.connect(MQTT_HOST, MQTT_PORT, 60)
            client.loop_start()
            self._client = client
        except Exception as exc:  # noqa: BLE001 — surface broker errors to the log
            self.events.publish(
                VehicleEvent.create(
                    SYSTEM_LOG,
                    source="mqtt",
                    severity="WARNING",
                    payload={"message": f"MQTT connect failed: {exc}"},
                )
            )

    def publish_command(self, payload: str) -> bool:
        if not self._client or not self.connected:
            return False
        self._client.publish(MQTT_TOPIC_COMMANDS, payload)
        return True

    def _on_connect(self, client, userdata, flags, reason_code, properties=None) -> None:  # noqa: ANN001
        self.connected = True
        self.state.set_service_flags(mqtt=True)
        client.subscribe(MQTT_TOPIC_EVENTS)

    def _on_message(self, client, userdata, message) -> None:  # noqa: ANN001
        # HardwareAdapter.ingest will be called from EngineeringPlatform when wired.
        self.events.publish(
            VehicleEvent.create(
                SYSTEM_LOG,
                source="mqtt",
                payload={"topic": message.topic, "bytes": len(message.payload)},
            )
        )

    def stop(self) -> None:
        if self._client:
            try:
                self._client.loop_stop()
                self._client.disconnect()
            except Exception:
                pass
        self.connected = False
        self.state.set_service_flags(mqtt=False)
