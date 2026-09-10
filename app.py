"""SDV Engineering Console — entry point.

Wires the window together and drives the 250ms Central State tick. Every
button/action in every view goes through `platform` (EngineeringPlatform);
this file never touches VehicleState, an adapter, or a service directly.
"""

from __future__ import annotations

import customtkinter as ctk

from sdv_console.components.content import ContentPanel
from sdv_console.components.header import Header
from sdv_console.components.sidebar import Sidebar
from sdv_console.components.status_bar import StatusBar
from sdv_console.config import APP_TITLE, COLORS, MIN_WINDOW_HEIGHT, MIN_WINDOW_WIDTH, TICK_MS, WINDOW_HEIGHT, WINDOW_WIDTH
from sdv_console.platform import EngineeringPlatform

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class ConsoleApp(ctk.CTk):
    def __init__(self) -> None:
        super().__init__()
        self.title(APP_TITLE)
        self.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        self.minsize(MIN_WINDOW_WIDTH, MIN_WINDOW_HEIGHT)
        self.configure(fg_color=COLORS["bg_primary"])

        self.platform = EngineeringPlatform()
        self.platform.start()

        self.header = Header(self, self.platform)
        self.header.pack(fill="x", side="top")

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, side="top")

        # 1. Instantiate self.content FIRST
        self.content = ContentPanel(body, self.platform)
        self.content.pack(fill="both", expand=True, side="right")

        # 2. Instantiate self.sidebar SECOND
        self.sidebar = Sidebar(body, on_navigate=self._navigate)
        self.sidebar.pack(fill="y", side="left")

        self.status_bar = StatusBar(self, self.platform)
        self.status_bar.pack(fill="x", side="bottom")

        self.protocol("WM_DELETE_WINDOW", self._on_close)

        try:
            from sdv_console.services.rest_api import run_rest_thread
            run_rest_thread(self.platform)
        except ImportError:
            pass

        self._tick()

    def _navigate(self, route: str) -> None:
        self.content.show(route)

    def _tick(self) -> None:
        self.platform.tick(TICK_MS / 1000.0)
        self.header.refresh()
        self.status_bar.refresh()
        self.content.refresh_active()
        self.after(TICK_MS, self._tick)

    def _on_close(self) -> None:
        self.platform.shutdown()
        self.destroy()


if __name__ == "__main__":
    app = ConsoleApp()
    app.mainloop()