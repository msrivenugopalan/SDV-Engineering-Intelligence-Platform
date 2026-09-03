"""DBC / vehicle network dictionary (project-specific, not a production parser)."""

import customtkinter as ctk

from sdv_console.components.widgets import caption, section_title
from sdv_console.config import COLORS
from sdv_console.platform import EngineeringPlatform
from sdv_console.services.dbc import messages


class DBCView(ctk.CTkScrollableFrame):
    def __init__(self, master, platform: EngineeringPlatform, **kwargs) -> None:
        super().__init__(master, fg_color=COLORS["bg_primary"], corner_radius=0, **kwargs)
        self.platform = platform
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=24, pady=16)
        section_title(head, "DBC / Vehicle Network").pack(anchor="w")
        caption(
            head,
            "Lightweight DBC-style dictionary used by this project. It is not an industry DBC parser. "
            "STM32 firmware should pack signals using these start-bit / factor / offset rules.",
        ).pack(anchor="w", pady=(0, 8))

        for msg in messages():
            card = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=10)
            card.pack(fill="x", padx=24, pady=6)
            ctk.CTkLabel(
                card,
                text=f"{msg['id_hex']}  {msg['name']}  ·  sender {msg['sender']}  ·  DLC {msg['dlc']}",
                font=ctk.CTkFont(size=14, weight="bold"),
                text_color=COLORS["accent_blueprint"],
            ).pack(anchor="w", padx=14, pady=(10, 4))
            for sig in msg["signals"]:
                ctk.CTkLabel(
                    card,
                    text=(
                        f"{sig['name']}: start {sig['start_bit']}, len {sig['length']}, "
                        f"factor {sig['factor']}, offset {sig['offset']} {sig['unit']}"
                    ),
                    font=ctk.CTkFont(size=12),
                    text_color=COLORS["text_secondary"],
                ).pack(anchor="w", padx=14, pady=1)
            ctk.CTkLabel(card, text="", height=8).pack()

    def refresh(self) -> None:
        return
