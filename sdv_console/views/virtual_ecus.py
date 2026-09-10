"""Virtual ECUs (architecture doc §5B / §6). Each tile maps 1:1 to a future
FreeRTOS task on the STM32 (EngineTask, BatteryTask, ...).
"""

from __future__ import annotations

import customtkinter as ctk

from sdv_console.components.widgets import caption, section_title, status_color
from sdv_console.config import COLORS


class VirtualECUsView(ctk.CTkScrollableFrame):
    def __init__(self, master, platform, **kwargs) -> None:
        super().__init__(master, fg_color=COLORS["bg_primary"], corner_radius=0, **kwargs)
        self.platform = platform
        self._rows: dict[str, dict] = {}
        self._build()

    def _build(self) -> None:
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=24, pady=16)
        section_title(head, "Virtual ECUs").pack(anchor="w")
        caption(head, "Each ECU here corresponds to a FreeRTOS task on the STM32F446RE. Name / Status / Firmware / Health / Last Update — one row per subsystem.").pack(anchor="w")

        self._grid = ctk.CTkFrame(self, fg_color="transparent")
        self._grid.pack(fill="x", padx=24, pady=8)
        headers = ["ECU", "FreeRTOS Task", "Status", "Health", "Firmware", "Last Event", "Last Update"]
        widths = (2, 2, 1, 2, 1, 3, 2)
        for i, wgt in enumerate(widths):
            self._grid.grid_columnconfigure(i, weight=wgt)
        for i, htext in enumerate(headers):
            ctk.CTkLabel(self._grid, text=htext, font=ctk.CTkFont(size=10, weight="bold"), text_color=COLORS["text_muted"]).grid(row=0, column=i, sticky="w", padx=8, pady=(0, 8))

        for r, ecu_id in enumerate(["engine", "battery", "brake", "steering", "climate", "adas"], start=1):
            row_frame = ctk.CTkFrame(self._grid, fg_color=COLORS["bg_card"] if r % 2 else COLORS["bg_card_alt"], corner_radius=6)
            row_frame.grid(row=r, column=0, columnspan=7, sticky="ew", pady=2)
            for c in range(7):
                row_frame.grid_columnconfigure(c, weight=1)

            name = ctk.CTkLabel(row_frame, text="—", font=ctk.CTkFont(size=12, weight="bold"), anchor="w")
            name.grid(row=0, column=0, sticky="w", padx=8, pady=8)
            task = ctk.CTkLabel(row_frame, text="—", font=ctk.CTkFont(family="Consolas", size=11), text_color=COLORS["text_secondary"], anchor="w")
            task.grid(row=0, column=1, sticky="w", padx=8)
            status = ctk.CTkLabel(row_frame, text="—", font=ctk.CTkFont(family="Consolas", size=11, weight="bold"), anchor="w")
            status.grid(row=0, column=2, sticky="w", padx=8)
            bar = ctk.CTkProgressBar(row_frame, height=8, width=90)
            bar.grid(row=0, column=3, sticky="w", padx=8)
            bar.set(0)
            fw = ctk.CTkLabel(row_frame, text="—", font=ctk.CTkFont(family="Consolas", size=11), text_color=COLORS["text_secondary"], anchor="w")
            fw.grid(row=0, column=4, sticky="w", padx=8)
            last_event = ctk.CTkLabel(row_frame, text="—", font=ctk.CTkFont(size=11), text_color=COLORS["text_secondary"], anchor="w")
            last_event.grid(row=0, column=5, sticky="w", padx=8)
            updated = ctk.CTkLabel(row_frame, text="—", font=ctk.CTkFont(family="Consolas", size=10), text_color=COLORS["text_muted"], anchor="w")
            updated.grid(row=0, column=6, sticky="w", padx=8)

            self._rows[ecu_id] = {"name": name, "task": task, "status": status, "bar": bar, "fw": fw, "event": last_event, "updated": updated}

    def refresh(self) -> None:
        snap = self.platform.snapshot()
        for ecu_id, widgets in self._rows.items():
            ecu = snap["ecus"].get(ecu_id)
            if not ecu:
                continue
            color = status_color(ecu["status"])
            widgets["name"].configure(text=ecu["name"])
            widgets["task"].configure(text=ecu["task"] + "()")
            widgets["status"].configure(text=ecu["status"], text_color=color)
            widgets["bar"].set(max(0, min(100, ecu["health"])) / 100)
            widgets["bar"].configure(progress_color=color)
            widgets["fw"].configure(text=ecu["firmware"])
            widgets["event"].configure(text=ecu["last_event"])
            ts = (ecu.get("last_update") or "")[11:19]
            widgets["updated"].configure(text=ts or "—")
