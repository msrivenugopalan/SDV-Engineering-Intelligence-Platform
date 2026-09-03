"""Event / fault history from SQLite."""

import customtkinter as ctk

from sdv_console.components.widgets import caption, section_title
from sdv_console.config import COLORS, ECU_CATALOG
from sdv_console.platform import EngineeringPlatform


class HistoryView(ctk.CTkFrame):
    def __init__(self, master, platform: EngineeringPlatform, **kwargs) -> None:
        super().__init__(master, fg_color=COLORS["bg_primary"], corner_radius=0, **kwargs)
        self.platform = platform
        self._ecu = ctk.StringVar(value="all")
        self._type = ctk.StringVar(value="all")
        self._build()

    def _build(self) -> None:
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=24, pady=16)
        section_title(head, "Event / Fault History").pack(anchor="w")
        caption(head, "Persisted in SQLite. High-rate CAN/telemetry samples are not stored on every tick.").pack(anchor="w")

        filters = ctk.CTkFrame(self, fg_color="transparent")
        filters.pack(fill="x", padx=24, pady=8)
        ctk.CTkLabel(filters, text="ECU", text_color=COLORS["text_muted"]).pack(side="left")
        ctk.CTkOptionMenu(
            filters,
            variable=self._ecu,
            values=["all"] + [e["id"] for e in ECU_CATALOG],
            width=140,
            command=lambda _v: self.refresh(),
        ).pack(side="left", padx=8)
        ctk.CTkLabel(filters, text="Event type", text_color=COLORS["text_muted"]).pack(side="left", padx=(16, 0))
        ctk.CTkOptionMenu(
            filters,
            variable=self._type,
            values=["all", "BATTERY_FAULT_DETECTED", "ECU_RECOVERY_SUCCESS", "OTA_COMPLETED", "VOICE_COMMAND", "SYSTEM_LOG"],
            width=220,
            command=lambda _v: self.refresh(),
        ).pack(side="left", padx=8)

        self._box = ctk.CTkTextbox(self, fg_color=COLORS["bg_card"], font=ctk.CTkFont(family="Consolas", size=12))
        self._box.pack(fill="both", expand=True, padx=24, pady=(0, 20))
        self._stamp = None

    def refresh(self) -> None:
        ecu = None if self._ecu.get() == "all" else self._ecu.get()
        et = None if self._type.get() == "all" else self._type.get()
        rows = self.platform.history.query_events(ecu=ecu, event_type=et, limit=150)
        stamp = (ecu, et, rows[0]["id"] if rows else 0)
        if stamp == self._stamp:
            return
        self._stamp = stamp
        self._box.delete("1.0", "end")
        self._box.insert("end", f"{'Time':<26} {'Type':<28} {'ECU':<14} {'Sev':<8} Source\n")
        for row in rows:
            self._box.insert(
                "end",
                f"{str(row['timestamp'])[:23]:<26} {row['event_type']:<28} {str(row['ecu'] or '-'):<14} {row['severity']:<8} {row['source']}\n",
            )
