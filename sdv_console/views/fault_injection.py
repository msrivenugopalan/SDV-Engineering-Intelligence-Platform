"""Fault injection — commands go to the active adapter (sim or hardware)."""

import customtkinter as ctk

from sdv_console.components.widgets import caption, section_title
from sdv_console.config import COLORS, FAULT_CATALOG
from sdv_console.platform import EngineeringPlatform


class FaultInjectionView(ctk.CTkScrollableFrame):
    def __init__(self, master, platform: EngineeringPlatform, **kwargs) -> None:
        super().__init__(master, fg_color=COLORS["bg_primary"], corner_radius=0, **kwargs)
        self.platform = platform
        self._result = None
        self._build()

    def _build(self) -> None:
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=24, pady=16)
        section_title(head, "Fault Injection").pack(anchor="w")
        caption(
            head,
            "Selecting a fault sends a command into the Vehicle State Manager. In SIMULATION MODE the adapter applies "
            "the fault locally. In hardware mode the same command is queued for STM32 FaultManagerTask() via ESP32.",
        ).pack(anchor="w", pady=(0, 12))

        grid = ctk.CTkFrame(self, fg_color="transparent")
        grid.pack(fill="x", padx=24)
        for i, (ecu_id, spec) in enumerate(FAULT_CATALOG.items()):
            card = ctk.CTkFrame(grid, fg_color=COLORS["bg_card"], corner_radius=10)
            card.grid(row=i // 2, column=i % 2, sticky="nsew", padx=6, pady=6)
            grid.grid_columnconfigure(i % 2, weight=1)
            ctk.CTkLabel(card, text=spec["label"], font=ctk.CTkFont(size=15, weight="bold"), text_color=COLORS["text_primary"]).pack(
                anchor="w", padx=12, pady=(10, 2)
            )
            ctk.CTkLabel(card, text=spec["fault_id"], font=ctk.CTkFont(size=12), text_color=COLORS["error"]).pack(anchor="w", padx=12)
            ctk.CTkLabel(card, text=spec["description"], font=ctk.CTkFont(size=12), text_color=COLORS["text_muted"], wraplength=420, justify="left").pack(
                anchor="w", padx=12, pady=4
            )
            ctk.CTkButton(
                card,
                text="Inject",
                width=120,
                command=lambda e=ecu_id: self._inject(e),
            ).pack(anchor="e", padx=12, pady=(4, 12))

        self._result = ctk.CTkLabel(self, text="", font=ctk.CTkFont(size=13), text_color=COLORS["text_secondary"])
        self._result.pack(anchor="w", padx=24, pady=8)

    def _inject(self, ecu_id: str) -> None:
        result = self.platform.inject_fault(ecu_id)
        if result.get("ok"):
            self._result.configure(
                text=f"Injected {result.get('fault_id')}. Diagnostics + ARI are driven from the event bus.",
                text_color=COLORS["warning"],
            )
        else:
            self._result.configure(text=str(result), text_color=COLORS["error"])

    def refresh(self) -> None:
        return
