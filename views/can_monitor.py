"""CAN monitor."""

import customtkinter as ctk

from sdv_console.components.cards import StatCard
from sdv_console.components.widgets import caption, section_title
from sdv_console.config import COLORS
from sdv_console.platform import EngineeringPlatform


class CANMonitorView(ctk.CTkFrame):
    def __init__(self, master, platform: EngineeringPlatform, **kwargs) -> None:
        super().__init__(master, fg_color=COLORS["bg_primary"], corner_radius=0, **kwargs)
        self.platform = platform
        self._stats: list[StatCard] = []
        self._build()

    def _build(self) -> None:
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=24, pady=16)
        section_title(head, "CAN Monitor").pack(anchor="w")
        caption(
            head,
            "Frames use the project DBC IDs (0x101–0x106). Simulated RX today; STM32 CAN TX should emit the same IDs later.",
        ).pack(anchor="w")

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=24)
        for i, label in enumerate(["Bus status", "Message count", "Error count", "Last message"]):
            card = StatCard(row, label, "—")
            card.pack(side="left", expand=True, fill="x", padx=(0 if i == 0 else 6, 0))
            self._stats.append(card)

        self._box = ctk.CTkTextbox(self, font=ctk.CTkFont(family="Consolas", size=12), fg_color=COLORS["bg_card"])
        self._box.pack(fill="both", expand=True, padx=24, pady=16)

    def refresh(self) -> None:
        snap = self.platform.snapshot()
        bus = snap["can"]
        self._stats[0].set_value(bus["bus_state"], COLORS["error"] if bus["bus_state"] != "OK" else COLORS["success"])
        self._stats[1].set_value(str(bus["message_count"]))
        self._stats[2].set_value(str(bus["error_count"]))
        self._stats[3].set_value(str(bus["last_message"]))
        self._box.delete("1.0", "end")
        header = f"{'Time':<28} {'ID':<8} {'ECU':<16} {'Message':<16} {'Dir':<4} {'St':<6} Data\n"
        self._box.insert("end", header)
        for frame in reversed(snap["can_frames"][-40:]):
            ts = frame["timestamp"][11:23]
            line = (
                f"{ts:<28} {frame['can_id']:<8} {frame['ecu']:<16} {frame['message']:<16} "
                f"{frame['direction']:<4} {frame['status']:<6} {frame['data']}\n"
            )
            self._box.insert("end", line)
