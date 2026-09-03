"""Manages hardware and service connection state for the console."""

from collections.abc import Callable


class ConnectionState:
    """Tracks STM32 connection and propagates changes to UI listeners."""

    def __init__(self) -> None:
        self._stm32_connected = False
        self._listeners: list[Callable[["ConnectionState"], None]] = []

    @property
    def stm32_connected(self) -> bool:
        return self._stm32_connected

    @property
    def is_connected(self) -> bool:
        """True when the vehicle dashboard has an active STM32 link."""
        return self._stm32_connected

    def add_listener(self, callback: Callable[["ConnectionState"], None]) -> None:
        self._listeners.append(callback)

    def remove_listener(self, callback: Callable[["ConnectionState"], None]) -> None:
        if callback in self._listeners:
            self._listeners.remove(callback)

    def set_stm32_connected(self, connected: bool) -> None:
        """Update STM32 link state. Called by future hardware integration."""
        if self._stm32_connected == connected:
            return
        self._stm32_connected = connected
        self._notify()

    def connect_stm32(self) -> None:
        """Stub for future STM32 connection handler."""
        self.set_stm32_connected(True)

    def disconnect_stm32(self) -> None:
        """Stub for future STM32 disconnection handler."""
        self.set_stm32_connected(False)

    def _notify(self) -> None:
        for callback in self._listeners:
            callback(self)
