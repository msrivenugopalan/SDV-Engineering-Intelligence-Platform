"""CAN / DBC Monitor (architecture doc §7). The frame log only rebuilds
when new traffic actually arrived (message_count changed) — same pattern
used everywhere state-driven text needs to stay smooth at 4Hz.
"""

from __future__ import annotations

import customtkinter as ctk

from sdv_console.components.widgets import StatCard, caption, section_title
from sdv_console.config import COLORS, DBC_CATALOG


class CANMonitorView(ctk.CTkScrollableFrame):
    def __init__(self, master, platform, **kwargs) -> None:
        super().__init__(master, fg_color=COLORS["bg_primary"], corner_radius=0, **kwargs)
        self.platform = platform
        self._stamp = None
        self._build()

    def _build(self) -> None:
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=24, pady=16)
        section_title(head, "CAN / DBC Monitor").pack(anchor="w")
        caption(head, "In-memory DBC decode: CAN ID → Message → Signal → Factor/Offset → Unit → Sender/Receiver. "
                       "This is a stand-in for a real .dbc file (see config.DBC_CATALOG).").pack(anchor="w")

        stat_row = ctk.CTkFrame(self, fg_color="transparent")
        stat_row.pack(fill="x", padx=24, pady=(0, 8))
        self._stats: dict[str, StatCard] = {}
        for i, (key, label) in enumerate([("state", "Bus State"), ("rate", "Messages/sec"), ("errors", "Error Count"), ("load", "Bus Load"), ("total", "Total Frames")]):
            card = StatCard(stat_row, label, "—")
            card.grid(row=0, column=i, sticky="nsew", padx=4)
            stat_row.grid_columnconfigure(i, weight=1)
            self._stats[key] = card

        section_title(self, "Frame Log").pack(anchor="w", padx=24, pady=(12, 4))
        self._box = ctk.CTkTextbox(self, height=260, fg_color=COLORS["bg_card"], font=ctk.CTkFont(family="Consolas", size=12))
        self._box.pack(fill="x", padx=24, pady=(0, 16))

        section_title(self, "DBC Signal Catalog").pack(anchor="w", padx=24, pady=(4, 4))
        table = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=8)
        table.pack(fill="x", padx=24, pady=(0, 24))
        headers = ["CAN ID", "Message", "Signal", "Factor", "Offset", "Unit", "Sender", "Receiver"]
        for i, h in enumerate(headers):
            table.grid_columnconfigure(i, weight=1)
            ctk.CTkLabel(table, text=h, font=ctk.CTkFont(size=10, weight="bold"), text_color=COLORS["text_muted"]).grid(row=0, column=i, sticky="w", padx=8, pady=(10, 4))
        for r, row in enumerate(DBC_CATALOG, start=1):
            for c, key in enumerate(["can_id", "message", "signal", "factor", "offset", "unit", "sender", "receiver"]):
                ctk.CTkLabel(table, text=str(row[key]), font=ctk.CTkFont(family="Consolas", size=11), text_color=COLORS["text_secondary"]).grid(row=r, column=c, sticky="w", padx=8, pady=2)

    def refresh(self) -> None:
        snap = self.platform.snapshot()
        can = snap["can"]
        color = COLORS["error"] if can["bus_state"] == "ERROR" else COLORS["success"] if can["bus_state"] == "ACTIVE" else COLORS["text_muted"]
        self._stats["state"].set_value(can["bus_state"], color)
        self._stats["rate"].set_value(f"{can['messages_per_sec']:.0f}")
        self._stats["errors"].set_value(str(can["error_count"]), COLORS["error"] if can["error_count"] else COLORS["success"])
        self._stats["load"].set_value(f"{can['bus_load_pct']:.0f}%")
        self._stats["total"].set_value(str(can["message_count"]))

        stamp = (can["message_count"], can["bus_state"])
        if stamp == self._stamp:
            return
        self._stamp = stamp

        self._box.delete("1.0", "end")
        self._box.insert("end", f"{'Time':<16} {'ID':<8} {'ECU':<14} {'Message':<16} {'Dir':<4} {'St':<6} Data\n")
        for frame in reversed(snap["can_frames"][-40:]):
            ts = frame["timestamp"][11:23]
            self._box.insert("end", f"{ts:<16} {frame['can_id']:<8} {frame['ecu']:<14} {frame['message']:<16} {frame['direction']:<4} {frame['status']:<6} {frame['data']}\n")
