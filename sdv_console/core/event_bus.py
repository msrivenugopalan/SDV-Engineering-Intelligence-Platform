"""Event bus — the "Events" node in the architecture diagram.

Central State publishes here whenever something changes; History, ARI, and
any other interested module subscribe. Subscribing with event_type=None
means "every event" (History uses this to log everything).
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable

from sdv_console.core.models import VehicleEvent

Handler = Callable[[VehicleEvent], None]


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str | None, list[Handler]] = defaultdict(list)

    def subscribe(self, event_type: str | None, handler: Handler) -> None:
        self._subscribers[event_type].append(handler)

    def publish(self, event: VehicleEvent) -> None:
        for handler in self._subscribers.get(event.event_type, []):
            handler(event)
        if event.event_type is not None:
            for handler in self._subscribers.get(None, []):
                handler(event)
