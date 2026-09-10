from __future__ import annotations

import customtkinter as ctk

from sdv_console.components.widgets import format_uptime
from sdv_console.config import APP_TITLE, APP_VERSION, COLORS


class Header(ctk.CTkFrame):
    def __init__(self, master, platform, **kwargs) -> None:
        super().__init__(master, fg_color=COLORS["bg_secondary"], corner_radius=0, height=64, **kwargs)
        self.platform = platform
        self.pack_propagate(False)

        left = ctk.CTkFrame(self, fg_color="transparent")
        left.pack(side="left", padx=20, pady=8)
        ctk.CTkLabel(left, text=APP_TITLE, font=ctk.CTkFont(family="Segoe UI", size=17, weight="bold"), text_color=COLORS["text_primary"]).pack(anchor="w")
        ctk.CTkLabel(left, text="Intelligent Software-Defined Vehicle Engineering Platform", font=ctk.CTkFont(size=10), text_color=COLORS["text_muted"]).pack(anchor="w")

        right = ctk.CTkFrame(self, fg_color="transparent")
        right.pack(side="right", padx=20)
        self._fields: dict[str, tuple[ctk.CTkLabel, ctk.CTkLabel]] = {}
        for key, label in [("gateway", "GATEWAY"), ("stm32", "STM32"), ("can", "CAN"), ("firmware", "FIRMWARE"), ("clock", "UPTIME")]:
            col = ctk.CTkFrame(right, fg_color="transparent")
            col.pack(side="left", padx=12)
            ctk.CTkLabel(col, text=label, font=ctk.CTkFont(size=8), text_color=COLORS["text_muted"]).pack()
            val = ctk.CTkLabel(col, text="—", font=ctk.CTkFont(family="Consolas", size=11, weight="bold"), text_color=COLORS["text_secondary"])
            val.pack()
            self._fields[key] = (col, val)

    def refresh(self) -> None:
        snap = self.platform.snapshot()
        svc = snap["services"]
        gw = "ESP32 \u2014 " + ("Connected" if svc["esp32"] else "Simulation" if snap["mode"] == "SIMULATION" else "Idle")
        self._fields["gateway"][1].configure(text=gw, text_color=COLORS["success"] if svc["esp32"] else COLORS["warning"])
        self._fields["stm32"][1].configure(text="Connected" if svc["stm32"] else "Not linked", text_color=COLORS["success"] if svc["stm32"] else COLORS["text_muted"])
        can = snap["can"]
        self._fields["can"][1].configure(text=f"{can['bus_state']} · {can['messages_per_sec']:.0f}/s", text_color=COLORS["error"] if can["bus_state"] == "ERROR" else COLORS["success"])
        self._fields["firmware"][1].configure(text=snap["firmware"], text_color=COLORS["accent"])
        self._fields["clock"][1].configure(text=format_uptime(snap["uptime_started"]))
