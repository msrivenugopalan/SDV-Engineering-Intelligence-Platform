"""Event bus. Modules subscribe here. Views must not call each other."""

from __future__ import annotations

from collections import deque
from collections.abc import Callable
from threading import RLock

from sdv_console.config import EVENT_BUFFER_SIZE
from sdv_console.core.events import VehicleEvent

Listener = Callable[[VehicleEvent], None]


class EventManager:
    """Publish/subscribe bus used by simulation and (later) hardware ingest."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._listeners: dict[str, list[Listener]] = {}
        self._global: list[Listener] = []
        self._recent: deque[VehicleEvent] = deque(maxlen=EVENT_BUFFER_SIZE)

    def subscribe(self, event_type: str | None, callback: Listener) -> None:
        """Subscribe to one event type, or pass None for all events."""
        with self._lock:
            if event_type is None:
                self._global.append(callback)
            else:
                self._listeners.setdefault(event_type, []).append(callback)

    def unsubscribe(self, callback: Listener) -> None:
        with self._lock:
            if callback in self._global:
                self._global.remove(callback)
            for listeners in self._listeners.values():
                if callback in listeners:
                    listeners.remove(callback)

    def publish(self, event: VehicleEvent) -> None:
        with self._lock:
            self._recent.append(event)
            targeted = list(self._listeners.get(event.event_type, []))
            global_listeners = list(self._global)
        for callback in targeted + global_listeners:
            callback(event)

    def recent(self, limit: int = 100, event_type: str | None = None, ecu: str | None = None) -> list[VehicleEvent]:
        with self._lock:
            items = list(self._recent)
        if event_type:
            items = [e for e in items if e.event_type == event_type]
        if ecu:
            items = [e for e in items if e.ecu == ecu]
        return items[-limit:]
