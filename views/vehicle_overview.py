"""Vehicle Overview — health, ECU cards, twin snapshot from live state."""

from __future__ import annotations

import customtkinter as ctk

from sdv_console.components.cards import StatCard
from sdv_console.components.digital_twin_blueprint import DigitalTwinBlueprint
from sdv_console.components.widgets import ECUCard, caption, section_title, status_color
from sdv_console.config import COLORS
from sdv_console.platform import EngineeringPlatform


class VehicleOverviewView(ctk.CTkScrollableFrame):
    def __init__(self, master, platform: EngineeringPlatform, **kwargs) -> None:
        super().__init__(master, fg_color=COLORS["bg_primary"], corner_radius=0, **kwargs)
        self.platform = platform
        self._stat_cards: list[StatCard] = []
        self._ecu_cards: dict[str, ECUCard] = {}
        self.grid_columnconfigure(0, weight=1)
        self._build()

    def _build(self) -> None:
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=24, pady=(16, 8))
        section_title(head, "Vehicle Overview").pack(anchor="w")
        caption(head, "SDV Engineering Prototype. Values below come from the Vehicle State Manager (simulation until STM32 is linked).").pack(anchor="w")

        stats = ctk.CTkFrame(self, fg_color="transparent")
        stats.grid(row=1, column=0, sticky="ew", padx=24, pady=8)
        for i in range(5):
            stats.grid_columnconfigure(i, weight=1)
        labels = ["Vehicle state", "Power", "Data source", "FreeRTOS", "Active faults"]
        for i, label in enumerate(labels):
            card = StatCard(stats, label, "—")
            card.grid(row=0, column=i, sticky="nsew", padx=(0 if i == 0 else 6, 0))
            self._stat_cards.append(card)

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=2, column=0, sticky="nsew", padx=24, pady=(8, 16))
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=1)

        ecu_wrap = ctk.CTkFrame(body, fg_color="transparent")
        ecu_wrap.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        section_title(ecu_wrap, "ECU health").pack(anchor="w", pady=(0, 8))
        grid = ctk.CTkFrame(ecu_wrap, fg_color="transparent")
        grid.pack(fill="both", expand=True)
        for i in range(2):
            grid.grid_columnconfigure(i, weight=1)
        for index, ecu_id in enumerate(["engine", "battery", "brake", "steering", "climate", "adas"]):
            card = ECUCard(grid)
            r, c = divmod(index, 2)
            card.grid(row=r, column=c, sticky="nsew", padx=4, pady=4)
            self._ecu_cards[ecu_id] = card

        self._twin = DigitalTwinBlueprint(body, self.platform.snapshot)
        self._twin.grid(row=0, column=1, sticky="nsew")

    def refresh(self) -> None:
        snap = self.platform.snapshot()
        values = [
            (snap["overall_health"], status_color(snap["overall_health"])),
            ("ON" if snap["mode"] != "DISCONNECTED" else "OFF", COLORS["success"] if snap["mode"] != "DISCONNECTED" else COLORS["error"]),
            (snap["connection_label"], COLORS["warning"] if snap["mode"] == "SIMULATION" else COLORS["text_primary"]),
            ("Simulated tasks" if snap["mode"] == "SIMULATION" else "Stopped", COLORS["text_primary"]),
            (str(len(snap["active_faults"])), COLORS["error"] if snap["active_faults"] else COLORS["success"]),
        ]
        for card, (value, color) in zip(self._stat_cards, values):
            card.set_value(value, color)
        for ecu_id, card in self._ecu_cards.items():
            if ecu_id in snap["ecus"]:
                card.update_from(snap["ecus"][ecu_id])
        self._twin.refresh()
