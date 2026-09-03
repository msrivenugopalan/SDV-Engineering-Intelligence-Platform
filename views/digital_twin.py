"""Dedicated digital twin page."""

import customtkinter as ctk

from sdv_console.components.digital_twin_blueprint import DigitalTwinBlueprint
from sdv_console.components.widgets import caption, section_title
from sdv_console.config import COLORS
from sdv_console.platform import EngineeringPlatform


class DigitalTwinView(ctk.CTkFrame):
    def __init__(self, master, platform: EngineeringPlatform, **kwargs) -> None:
        super().__init__(master, fg_color=COLORS["bg_primary"], corner_radius=0, **kwargs)
        self.platform = platform
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=24, pady=16)
        section_title(head, "Digital Twin").pack(anchor="w")
        caption(
            head,
            "2D software-state twin. Colors follow the same ECU status field used by diagnostics, ARI, and telemetry. "
            "This is not a 3D car model.",
        ).pack(anchor="w")
        self._twin = DigitalTwinBlueprint(self, platform.snapshot)
        self._twin.pack(fill="both", expand=True, padx=24, pady=(0, 24))

    def refresh(self) -> None:
        self._twin.refresh()
