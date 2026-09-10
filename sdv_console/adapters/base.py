"""Common interface for anything that can drive Central State.

Simulation and Hardware (STM32/ESP32) are interchangeable behind this
interface — Central State and every view don't know or care which one is
active. That's what makes "switch to hardware when it's ready" a flip of a
mode flag instead of a rewrite.
"""

from __future__ import annotations

from typing import Any


class VehicleSource:
    name = "base"

    def start(self) -> None: ...

    def stop(self) -> None: ...

    def tick(self, dt: float) -> None: ...

    def inject_fault(self, ecu_id: str) -> dict[str, Any]:
        return {"ok": False, "error": "not_supported"}

    def start_recovery(self, ecu_id: str) -> dict[str, Any]:
        return {"ok": False, "error": "not_supported"}

    def start_ota(self, target_ecu: str, target_version: str) -> dict[str, Any]:
        return {"ok": False, "error": "not_supported"}
