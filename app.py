"""Main application window."""

from __future__ import annotations
import sys
from pathlib import Path

# Get the exact absolute path of the folder containing app.py
PROJECT_ROOT = Path(__file__).resolve().parent

# Force Python to look in app.py's folder for modules FIRST
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
import customtkinter as ctk

try:
    import pyttsx3
except ImportError:  # optional; typed replies still work
    pyttsx3 = None

from sdv_console.components import ContentPanel, HeaderBar, Sidebar, SystemStatusBar
from sdv_console.config import (
    APP_TITLE,
    COLORS,
    MIN_WINDOW_HEIGHT,
    MIN_WINDOW_WIDTH,
    TICK_MS,
    WINDOW_HEIGHT,
    WINDOW_WIDTH,
)
from sdv_console.platform import EngineeringPlatform
from sdv_console.services.rest_api import run_rest_thread
from sdv_console.state import ConnectionState


class SDVEngineeringConsole(ctk.CTk):
    """Root application window for the SDV Engineering Console."""

    def __init__(self) -> None:
        super().__init__()

        self.platform = EngineeringPlatform()
        # Kept so existing STM32 hooks still exist; hardware truth lives on the platform.
        self.connection_state = ConnectionState()

        self.title(APP_TITLE)
        self.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.minsize(MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT)
        self.configure(fg_color=COLORS["bg_primary"])

        self._tts = None
        if pyttsx3 is not None:
            try:
                self._tts = pyttsx3.init()
            except Exception:
                self._tts = None

        self.platform.speak = self._speak
        self.platform.navigate = self._navigate

        self._configure_theme()
        self._build_layout()
        self.platform.start()
        try:
            run_rest_thread(self.platform)
        except OSError:
            pass

        self.protocol("WM_DELETE_WINDOW", self._on_close)
        self.after(TICK_MS, self._tick)

    @property
    def is_connected(self) -> bool:
        return self.platform.snapshot()["mode"] != "DISCONNECTED"

    def _configure_theme(self) -> None:
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

    def _build_layout(self) -> None:
        self.grid_rowconfigure(1, weight=1)
        self.grid_columnconfigure(1, weight=1)

        self._header = HeaderBar(self, self.platform)
        self._header.grid(row=0, column=0, columnspan=2, sticky="ew")

        separator = ctk.CTkFrame(self, height=1, fg_color=COLORS["border"], corner_radius=0)
        separator.grid(row=0, column=0, columnspan=2, sticky="sew")

        self._sidebar = Sidebar(self, on_select=self._navigate)
        self._sidebar.grid(row=1, column=0, sticky="nsw")

        sidebar_divider = ctk.CTkFrame(self, width=1, fg_color=COLORS["border"], corner_radius=0)
        sidebar_divider.grid(row=1, column=0, sticky="nse")

        self._content = ContentPanel(self, self.platform)
        self._content.grid(row=1, column=1, sticky="nsew")

        self._status_bar = SystemStatusBar(self, self.platform)
        self._status_bar.grid(row=2, column=0, columnspan=2, sticky="ew")

    def _navigate(self, page: str) -> None:
        # Do not call Sidebar.select() here — that callback would recurse.
        if getattr(self._sidebar, "_active", None) != page:
            self._sidebar._active = page
            self._sidebar._paint()
        self._content.show(page)

    def _tick(self) -> None:
        self.platform.tick(TICK_MS / 1000.0)
        self._header.refresh()
        self._status_bar.refresh()
        self._content.refresh_visible()
        self.after(TICK_MS, self._tick)

    def _speak(self, text: str) -> None:
        if not text or self._tts is None:
            return

        def _run() -> None:
            try:
                self._tts.say(text)
                self._tts.runAndWait()
            except Exception:
                pass

        import threading

        threading.Thread(target=_run, daemon=True).start()

    def _on_close(self) -> None:
        self.platform.shutdown()
        self.destroy()

    def on_stm32_connected(self) -> None:
        """Hook for future STM32 serial/USB connection handler."""
        self.connection_state.connect_stm32()
        self.platform.state.set_service_flags(stm32=True)

    def on_stm32_disconnected(self) -> None:
        """Hook for future STM32 disconnection handler."""
        self.connection_state.disconnect_stm32()
        self.platform.state.set_service_flags(stm32=False)
if __name__ == "__main__":
    app = SDVEngineeringConsole()
    app.mainloop()