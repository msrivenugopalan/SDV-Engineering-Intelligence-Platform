from __future__ import annotations

import customtkinter as ctk

from sdv_console.components.digital_twin import DigitalTwin
from sdv_console.components.widgets import caption, section_title
from sdv_console.config import COLORS


class DigitalTwinView(ctk.CTkFrame):
    def __init__(self, master, platform, **kwargs) -> None:
        super().__init__(master, fg_color=COLORS["bg_primary"], corner_radius=0, **kwargs)
        self.platform = platform
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=24, pady=16)
        section_title(head, "Digital Twin").pack(anchor="w")
        caption(head, "Not a picture of a car — a live visual of Central State. Battery ECU WARNING → node turns amber here, "
                       "a DTC appears on Diagnostics, and ARI generates an insight, all from the same event (architecture doc §9).").pack(anchor="w")
        self._twin = DigitalTwin(self, platform.snapshot, compact=False)
        self._twin.pack(fill="both", expand=True, padx=24, pady=(0, 24))

    def refresh(self) -> None:
        self._twin.refresh()
