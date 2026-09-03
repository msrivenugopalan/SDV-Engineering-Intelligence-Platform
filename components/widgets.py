"""Small shared UI helpers for the engineering console."""

from __future__ import annotations

import customtkinter as ctk

from sdv_console.config import COLORS, STATUS_COLORS


def section_title(parent, text: str) -> ctk.CTkLabel:
    return ctk.CTkLabel(
        parent,
        text=text,
        font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"),
        text_color=COLORS["text_primary"],
    )


def caption(parent, text: str) -> ctk.CTkLabel:
    return ctk.CTkLabel(
        parent,
        text=text,
        font=ctk.CTkFont(family="Segoe UI", size=12),
        text_color=COLORS["text_muted"],
        wraplength=900,
        justify="left",
        anchor="w",
    )


def status_color(status: str) -> str:
    return STATUS_COLORS.get(status, COLORS["text_primary"])


class ECUCard(ctk.CTkFrame):
    def __init__(self, master, **kwargs) -> None:
        super().__init__(
            master,
            fg_color=COLORS["bg_card"],
            border_color=COLORS["border"],
            border_width=1,
            corner_radius=10,
            **kwargs,
        )
        self._name = ctk.CTkLabel(self, text="", font=ctk.CTkFont(size=14, weight="bold"), text_color=COLORS["text_primary"])
        self._name.pack(anchor="w", padx=12, pady=(10, 2))
        self._status = ctk.CTkLabel(self, text="", font=ctk.CTkFont(size=13, weight="bold"))
        self._status.pack(anchor="w", padx=12)
        self._meta = ctk.CTkLabel(self, text="", font=ctk.CTkFont(size=11), text_color=COLORS["text_muted"], justify="left", anchor="w")
        self._meta.pack(anchor="w", padx=12, pady=(4, 12))

    def update_from(self, ecu: dict) -> None:
        self._name.configure(text=ecu["name"])
        self._status.configure(text=ecu["status"], text_color=status_color(ecu["status"]))
        last = ecu.get("last_update", "")[-12:].replace("T", " ")
        self._meta.configure(
            text=(
                f"Health {ecu['health']}%\n"
                f"Fault: {ecu.get('fault_id') or 'none'}\n"
                f"Recovery: {ecu.get('recovery_state')}\n"
                f"Updated: {last}"
            )
        )
