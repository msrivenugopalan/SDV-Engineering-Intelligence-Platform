from __future__ import annotations

import customtkinter as ctk

from sdv_console.components.widgets import StatCard, caption, section_title
from sdv_console.config import COLORS


class DiagnosticsView(ctk.CTkScrollableFrame):
    def __init__(self, master, platform, **kwargs) -> None:
        super().__init__(master, fg_color=COLORS["bg_primary"], corner_radius=0, **kwargs)
        self.platform = platform
        self._stamp = None
        self._build()

    def _build(self) -> None:
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=24, pady=16)
        section_title(head, "Diagnostics").pack(anchor="w")
        caption(head, "Fault/Event → DTC → Severity → Timestamp → History (architecture doc §11). Every DTC here traces back to a real fault injected or reported by hardware.").pack(anchor="w")

        stat_row = ctk.CTkFrame(self, fg_color="transparent")
        stat_row.pack(fill="x", padx=24, pady=(0, 12))
        self._stats: dict[str, StatCard] = {}
        for i, (key, label) in enumerate([("critical", "Critical"), ("warning", "Warning"), ("total", "Total DTCs")]):
            card = StatCard(stat_row, label, "0")
            card.grid(row=0, column=i, sticky="nsew", padx=4)
            stat_row.grid_columnconfigure(i, weight=1)
            self._stats[key] = card

        self._box = ctk.CTkTextbox(self, height=420, fg_color=COLORS["bg_card"], font=ctk.CTkFont(family="Consolas", size=12))
        self._box.pack(fill="both", expand=True, padx=24, pady=(0, 24))

    def refresh(self) -> None:
        diags = self.platform.snapshot()["diagnostics"]
        crit = sum(1 for d in diags if d["severity"] == "CRITICAL" and d["status"] == "ACTIVE")
        warn = sum(1 for d in diags if d["severity"] == "WARNING" and d["status"] == "ACTIVE")
        self._stats["critical"].set_value(str(crit), COLORS["error"] if crit else COLORS["success"])
        self._stats["warning"].set_value(str(warn), COLORS["warning"] if warn else COLORS["success"])
        self._stats["total"].set_value(str(len(diags)))

        stamp = tuple((d["dtc_id"], d["status"]) for d in diags)
        if stamp == self._stamp:
            return
        self._stamp = stamp

        self._box.delete("1.0", "end")
        if not diags:
            self._box.insert("end", "No DTC records.\n")
            return
        for d in diags:
            ts = (d.get("detected_at") or "")[11:19]
            self._box.insert("end", f"{ts}   {d['fault_id']:<22} {d['ecu']:<12} {d['severity']:<9} {d['status']}\n")
