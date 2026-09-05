"""In-memory system log (recent Event Manager stream)."""

import customtkinter as ctk

from sdv_console.components.widgets import caption, section_title
from sdv_console.config import COLORS
from sdv_console.platform import EngineeringPlatform


class SystemLogsView(ctk.CTkFrame):
    def __init__(self, master, platform: EngineeringPlatform, **kwargs) -> None:
        super().__init__(master, fg_color=COLORS["bg_primary"], corner_radius=0, **kwargs)
        self.platform = platform
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=24, pady=16)
        section_title(head, "System Logs").pack(anchor="w")
        caption(head, "Live event bus (includes frames suppressed from SQLite).").pack(anchor="w")
        self._box = ctk.CTkTextbox(self, fg_color=COLORS["bg_card"], font=ctk.CTkFont(family="Consolas", size=12))
        self._box.pack(fill="both", expand=True, padx=24, pady=(0, 20))
        self._stamp = None

    def refresh(self) -> None:
        events = [e for e in self.platform.events.recent(80) if e.event_type != "CAN_FRAME"]
        stamp = events[-1].correlation_id if events else None
        if stamp == self._stamp:
            return
        self._stamp = stamp
        self._box.delete("1.0", "end")
        for event in reversed(events):
            self._box.insert(
                "end",
                f"{event.timestamp[11:23]}  {event.event_type:<28}  {event.ecu or '-':<12}  {event.source}  {event.payload}\n",
            )
