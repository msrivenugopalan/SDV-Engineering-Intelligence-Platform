"""History (architecture doc §17) — the persisted, queryable counterpart to
System Logs. Throttled to at most 1 query/second (except on filter change)
since it's durable log data, not something that needs a fresh DB hit 4x/sec.
"""

from __future__ import annotations

import time

import customtkinter as ctk

from sdv_console.components.widgets import caption, section_title
from sdv_console.config import COLORS, ECU_CATALOG

QUERY_INTERVAL_S = 1.0


class HistoryView(ctk.CTkFrame):
    def __init__(self, master, platform, **kwargs) -> None:
        super().__init__(master, fg_color=COLORS["bg_primary"], corner_radius=0, **kwargs)
        self.platform = platform
        self._last_query_at = 0.0
        self._last_filters: tuple | None = None
        self._stamp = None
        self._build()

    def _build(self) -> None:
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=24, pady=16)
        section_title(head, "Event / Fault History").pack(anchor="w")
        caption(head, "Queryable, persisted event log — survives app restarts (SQLite, WAL mode).").pack(anchor="w")

        filters = ctk.CTkFrame(self, fg_color="transparent")
        filters.pack(fill="x", padx=24, pady=(0, 8))
        ctk.CTkLabel(filters, text="ECU", text_color=COLORS["text_muted"]).pack(side="left", padx=(0, 6))
        self._ecu = ctk.StringVar(value="all")
        ctk.CTkOptionMenu(filters, variable=self._ecu, values=["all"] + [e["id"] for e in ECU_CATALOG], width=140, command=lambda _v: self.refresh()).pack(side="left", padx=(0, 16))
        ctk.CTkLabel(filters, text="Event type", text_color=COLORS["text_muted"]).pack(side="left", padx=(0, 6))
        self._type = ctk.StringVar(value="all")
        types = ["all", "FAULT_DETECTED", "RECOVERY_STARTED", "RECOVERY_COMPLETED", "OTA_STARTED", "OTA_COMPLETED", "MODE_CHANGED", "VEHICLE_CONNECTED", "VEHICLE_DISCONNECTED", "SYSTEM_LOG"]
        ctk.CTkOptionMenu(filters, variable=self._type, values=types, width=180, command=lambda _v: self.refresh()).pack(side="left")

        self._box = ctk.CTkTextbox(self, fg_color=COLORS["bg_card"], font=ctk.CTkFont(family="Consolas", size=12))
        self._box.pack(fill="both", expand=True, padx=24, pady=(0, 24))

    def refresh(self) -> None:
        ecu = None if self._ecu.get() == "all" else self._ecu.get()
        et = None if self._type.get() == "all" else self._type.get()
        now = time.monotonic()
        filters_changed = (ecu, et) != self._last_filters
        if not filters_changed and now - self._last_query_at < QUERY_INTERVAL_S:
            return
        self._last_query_at = now
        self._last_filters = (ecu, et)

        rows = self.platform.history.query_events(ecu=ecu, event_type=et, limit=150)
        stamp = (ecu, et, rows[0]["id"] if rows else 0)
        if stamp == self._stamp:
            return
        self._stamp = stamp

        self._box.delete("1.0", "end")
        if not rows:
            self._box.insert("end", "No matching events.\n")
            return
        for r in rows:
            ts = (r.get("timestamp") or "")[11:19]
            ecu_txt = r.get("ecu") or "-"
            self._box.insert("end", f"{ts}  [{r.get('severity', 'INFO'):<8}] {r.get('event_type', ''):<22} ecu={ecu_txt}\n")
