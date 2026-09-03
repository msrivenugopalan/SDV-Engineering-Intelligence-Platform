"""Reusable statistic card widget."""

import customtkinter as ctk

from sdv_console.config import COLORS


class StatCard(ctk.CTkFrame):
    """Displays a labeled metric inside a styled card."""

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        label: str,
        value: str,
        *,
        value_color: str | None = None,
        **kwargs,
    ) -> None:
        super().__init__(
            master,
            fg_color=COLORS["bg_card"],
            border_color=COLORS["border"],
            border_width=1,
            corner_radius=10,
            **kwargs,
        )
        self._value_label: ctk.CTkLabel

        ctk.CTkLabel(
            self,
            text=label,
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=COLORS["text_muted"],
        ).pack(anchor="w", padx=14, pady=(12, 4))

        self._value_label = ctk.CTkLabel(
            self,
            text=value,
            font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"),
            text_color=value_color or COLORS["text_primary"],
        )
        self._value_label.pack(anchor="w", padx=14, pady=(0, 12))

    def set_value(self, value: str, value_color: str | None = None) -> None:
        self._value_label.configure(
            text=value,
            text_color=value_color or COLORS["text_primary"],
        )
