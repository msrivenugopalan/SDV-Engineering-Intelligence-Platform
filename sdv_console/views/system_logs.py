from __future__ import annotations

import customtkinter as ctk

from sdv_console.components.widgets import caption, section_title
from sdv_console.config import COLORS


class SystemLogsView(ctk.CTkFrame):
    def __init__(self, master, platform, **kwargs) -> None:
        super().__init__(master, fg_color=COLORS["bg_primary"], corner_radius=0, **kwargs)
        self.platform = platform
        self._stamp = None
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=24, pady=16)
        section_title(head, "System Logs").pack(anchor="w")
        caption(head, "The raw Event Bus stream — everything published anywhere in the app, in real time. "
                       "For a persisted, filterable, queryable view, see the History page.").pack(anchor="w")
        self._box = ctk.CTkTextbox(self, fg_color=COLORS["bg_card"], font=ctk.CTkFont(family="Consolas", size=12))
        self._box.pack(fill="both", expand=True, padx=24, pady=(0, 24))

    def refresh(self) -> None:
        events = self.platform.snapshot()["recent_events"]
        stamp = len(events)
        if stamp == self._stamp:
            return
        self._stamp = stamp
        self._box.delete("1.0", "end")
        for e in events[:150]:
            ts = (e.get("timestamp") or "")[11:23]
            ecu = e.get("ecu") or "-"
            self._box.insert("end", f"{ts}  [{e.get('severity', 'INFO'):<8}] {e.get('event_type', ''):<22} src={e.get('source', ''):<12} ecu={ecu}\n")
