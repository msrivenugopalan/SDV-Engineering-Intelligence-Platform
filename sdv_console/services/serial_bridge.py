"""Direct STM32 USB-serial receiver for the SDV dashboard.

Reads newline-delimited JSON in a background thread. It deliberately accepts
only telemetry objects with at least one known telemetry field, so startup
text and unrelated JSON cannot switch the platform into hardware mode.
"""

from __future__ import annotations

import json
import logging
import threading
from typing import Any, Callable

logger = logging.getLogger(__name__)

TELEMETRY_FIELDS = {
    "vehicle_speed",
    "battery_soc",
    "battery_voltage",
    "battery_current",
    "battery_power",
    "estimated_range",
    "engine_temp",
    "cabin_temp",
    "brake_status",
    "steering_status",
    "adas_status",
    "vehicle_state",
    "fault",
    "recovery_active",
}


class SerialBridge:
    """Reconnectable serial reader. The callback runs on its worker thread."""

    def __init__(
        self,
        on_telemetry: Callable[[dict[str, Any]], None],
        port: str = "COM9",
        baudrate: int = 115200,
        reconnect_delay_s: float = 2.0,
    ) -> None:
        self._on_telemetry = on_telemetry
        self.port = port
        self.baudrate = baudrate
        self.reconnect_delay_s = reconnect_delay_s
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._serial = None
        self._serial_lock = threading.Lock()
        self._last_error: str | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="STM32SerialBridge",
            daemon=True,
        )
        self._thread.start()
        logger.info("STM32 serial bridge started for %s at %d baud", self.port, self.baudrate)

    def stop(self) -> None:
        self._stop_event.set()
        with self._serial_lock:
            serial_port = self._serial
        if serial_port is not None:
            try:
                serial_port.close()
            except Exception:
                logger.debug("Error closing STM32 serial port", exc_info=True)
        thread = self._thread
        if thread and thread.is_alive() and thread is not threading.current_thread():
            thread.join(timeout=3.0)
        self._thread = None
        logger.info("STM32 serial bridge stopped")

    @staticmethod
    def _parse_telemetry(raw_line: bytes | str) -> dict[str, Any] | None:
        try:
            if isinstance(raw_line, bytes):
                line = raw_line.decode("utf-8", errors="strict").strip()
            else:
                line = raw_line.strip()
            if not line:
                return None
            message = json.loads(line)
        except (UnicodeDecodeError, json.JSONDecodeError, TypeError, ValueError):
            return None

        if not isinstance(message, dict) or message.get("type") != "telemetry":
            return None
        if not any(key in message for key in TELEMETRY_FIELDS):
            return None
        return message

    def _run(self) -> None:
        while not self._stop_event.is_set():
            try:
                # Import lazily: the desktop app remains usable if pyserial is absent.
                import serial

                serial_port = serial.Serial(
                    port=self.port,
                    baudrate=self.baudrate,
                    timeout=1.0,
                    write_timeout=1.0,
                )
                with self._serial_lock:
                    self._serial = serial_port
                self._last_error = None
                logger.info("STM32 serial connected on %s", self.port)

                try:
                    while not self._stop_event.is_set():
                        raw_line = serial_port.readline()
                        if not raw_line:
                            continue
                        message = self._parse_telemetry(raw_line)
                        if message is None:
                            # Ignore boot text, partial lines, and unrelated JSON.
                            continue
                        try:
                            self._on_telemetry(message)
                        except Exception:
                            logger.exception("Failed to deliver STM32 telemetry to the platform")
                finally:
                    with self._serial_lock:
                        if self._serial is serial_port:
                            self._serial = None
                    try:
                        serial_port.close()
                    except Exception:
                        pass
                    if not self._stop_event.is_set():
                        logger.warning("STM32 serial connection on %s ended; will reconnect", self.port)

            except Exception as exc:
                # Log a repeated failure only when its text changes, avoiding console floods.
                description = f"{type(exc).__name__}: {exc}"
                if description != self._last_error and not self._stop_event.is_set():
                    logger.warning("STM32 serial unavailable on %s (%s); retrying", self.port, description)
                    self._last_error = description
            self._stop_event.wait(self.reconnect_delay_s)
