"""Vehicle data-source interface.

SimulationAdapter and HardwareAdapter must both implement this so the
dashboard never talks to a simulator or UART driver directly.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class VehicleSource(ABC):
    """Commands go out; telemetry/events come in via VehicleStateManager."""

    name: str = "base"

    @abstractmethod
    def start(self) -> None: ...

    @abstractmethod
    def stop(self) -> None: ...

    @abstractmethod
    def tick(self, dt: float) -> None: ...

    @abstractmethod
    def inject_fault(self, ecu_id: str, correlation_id: str | None = None) -> dict[str, Any]: ...

    @abstractmethod
    def start_recovery(self, ecu_id: str | None = None) -> dict[str, Any]: ...

    @abstractmethod
    def start_ota(self, target_ecu: str, target_version: str) -> dict[str, Any]: ...
