"""Settings — Simulation vs Hardware mode switch (architecture doc §18) and
a live readout of every service flag.
"""

from __future__ import annotations

import customtkinter as ctk

from sdv_console.components.widgets import caption, section_title
from sdv_console.config import COLORS, MQTT_HOST, REST_HOST, REST_PORT


class SettingsView(ctk.CTkFrame):
    def __init__(self, master, platform, **kwargs) -> None:
        super().__init__(master, fg_color=COLORS["bg_primary"], corner_radius=0, **kwargs)
        self.platform = platform
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=24, pady=16)
        section_title(head, "Settings").pack(anchor="w")
        caption(head, "Both Simulation and Hardware feed the same Central State interface (architecture doc §18) — "
                       "switching modes doesn't change what any view reads, only where the numbers come from.").pack(anchor="w")

        modes = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=10)
        modes.pack(fill="x", padx=24, pady=8)
        ctk.CTkLabel(modes, text="Mode", text_color=COLORS["text_muted"]).pack(anchor="w", padx=16, pady=(16, 4))
        row = ctk.CTkFrame(modes, fg_color="transparent")
        row.pack(fill="x", padx=16, pady=(0, 16))
        ctk.CTkButton(row, text="SIMULATION", command=lambda: self._switch("SIMULATION")).pack(side="left", padx=(0, 8))
        ctk.CTkButton(row, text="Try HARDWARE MODE", fg_color=COLORS["accent_muted"], command=lambda: self._switch("HARDWARE")).pack(side="left", padx=(0, 8))
        ctk.CTkButton(row, text="DISCONNECT", fg_color=COLORS["error"], hover_color="#B91C1C", command=lambda: self._switch("DISCONNECTED")).pack(side="left")
        self._mode_msg = ctk.CTkLabel(modes, text="", font=ctk.CTkFont(size=11), text_color=COLORS["text_muted"])
        self._mode_msg.pack(anchor="w", padx=16, pady=(0, 16))

        info_card = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=10)
        info_card.pack(fill="x", padx=24, pady=8)
        self._info = ctk.CTkLabel(info_card, text="", font=ctk.CTkFont(family="Consolas", size=12), justify="left", anchor="w")
        self._info.pack(padx=16, pady=16, anchor="w")

    def _switch(self, mode: str) -> None:
        res = self.platform.set_mode(mode)
        if res.get("ok"):
            self._mode_msg.configure(text=f"Mode set to {res.get('mode')}.", text_color=COLORS["success"])
        else:
            self._mode_msg.configure(text=f"{res.get('error')}: {res.get('detail', '')}", text_color=COLORS["error"])

    def refresh(self) -> None:
        snap = self.platform.snapshot()
        svc = snap["services"]
        stm32_note = "connected" if svc["stm32"] else "not connected — POST JSON to /hardware/ingest"
        esp32_note = "connected" if svc["esp32"] else "not connected"
        self._info.configure(text=(
            f"Mode:              {snap['mode']}\n"
            f"Connection label:  {snap['connection_label']}\n"
            f"Firmware:          {snap['firmware']}\n"
            f"STM32 linked:      {svc['stm32']}   ({stm32_note})\n"
            f"ESP32 linked:      {svc['esp32']}   ({esp32_note})\n"
            f"MQTT broker:       {MQTT_HOST or '(not configured)'}\n"
            f"MQTT connected:    {svc['mqtt']}\n"
            f"REST API:          {'http://' + REST_HOST + ':' + str(REST_PORT) if svc['rest'] else 'stopped'}\n"
            f"SQLite:            {svc['sqlite']}\n"
        ))
