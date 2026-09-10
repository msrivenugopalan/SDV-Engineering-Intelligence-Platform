from __future__ import annotations

import customtkinter as ctk

from sdv_console.components.widgets import format_uptime
from sdv_console.config import COLORS


class StatusBar(ctk.CTkFrame):
    def __init__(self, master, platform, **kwargs) -> None:
        super().__init__(master, fg_color=COLORS["bg_secondary"], corner_radius=0, height=28, **kwargs)
        self.platform = platform
        self.pack_propagate(False)
        self._label = ctk.CTkLabel(self, text="", font=ctk.CTkFont(family="Consolas", size=10), text_color=COLORS["text_muted"], anchor="w")
        self._label.pack(side="left", padx=16)
        self._mode_label = ctk.CTkLabel(self, text="", font=ctk.CTkFont(family="Consolas", size=10, weight="bold"), text_color=COLORS["warning"])
        self._mode_label.pack(side="right", padx=16)

    def refresh(self) -> None:
        snap = self.platform.snapshot()
        svc = snap["services"]
        can = snap["can"]
        text = (
            f"CAN \u25CF {can['bus_state']}   {can['messages_per_sec']:.0f} msg/s   {can['error_count']} errors   "
            f"STM32 \u25CF {'LINKED' if svc['stm32'] else 'SIM'}   ESP32 \u25CF {'LINKED' if svc['esp32'] else 'SIM'}   "
            f"MQTT \u25CF {'UP' if svc['mqtt'] else 'IDLE'}   REST \u25CF {'RUNNING' if svc['rest'] else 'STOPPED'}   "
            f"SQLite \u25CF {'READY' if svc['sqlite'] else 'DOWN'}   UP {format_uptime(snap['uptime_started'])}"
        )
        self._label.configure(text=text)
        mode_color = COLORS["warning"] if snap["mode"] == "SIMULATION" else COLORS["success"] if snap["mode"] == "HARDWARE" else COLORS["error"]
        self._mode_label.configure(text=f"{snap['mode']} MODE", text_color=mode_color)
