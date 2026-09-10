from __future__ import annotations

from collections.abc import Callable

import customtkinter as ctk

from sdv_console.config import APP_VERSION, COLORS, NAVIGATION

SIDEBAR_WIDTH = 240


class Sidebar(ctk.CTkScrollableFrame):
    def __init__(self, master, on_navigate: Callable[[str], None], **kwargs) -> None:
        super().__init__(master, fg_color=COLORS["bg_secondary"], corner_radius=0, width=SIDEBAR_WIDTH, **kwargs)
        self.on_navigate = on_navigate
        self._buttons: dict[str, ctk.CTkButton] = {}
        self._active = "overview"

        ctk.CTkLabel(self, text="NAVIGATION", font=ctk.CTkFont(size=10, weight="bold"), text_color=COLORS["text_muted"]).pack(anchor="w", padx=16, pady=(12, 6))

        for section, items in NAVIGATION:
            ctk.CTkLabel(self, text=section, font=ctk.CTkFont(size=9, weight="bold"), text_color=COLORS["accent"]).pack(anchor="w", padx=16, pady=(14, 4))
            for display, icon, route in items:
                btn = ctk.CTkButton(
                    self, text=f"  {icon}   {display}", anchor="w", height=32,
                    fg_color="transparent", hover_color=COLORS["bg_card_alt"],
                    text_color=COLORS["text_secondary"], font=ctk.CTkFont(size=12),
                    command=lambda r=route: self._select(r),
                )
                btn.pack(fill="x", padx=8, pady=1)
                self._buttons[route] = btn

        ctk.CTkLabel(self, text=f"Console v{APP_VERSION}", font=ctk.CTkFont(size=9), text_color=COLORS["text_muted"]).pack(anchor="w", padx=16, pady=(20, 2))
        ctk.CTkLabel(self, text="SIM \u2194 HW ready", font=ctk.CTkFont(size=9), text_color=COLORS["text_muted"]).pack(anchor="w", padx=16, pady=(0, 12))

        

    def _select(self, route: str) -> None:
        for r, btn in self._buttons.items():
            if r == route:
                btn.configure(fg_color=COLORS["accent_muted"], text_color=COLORS["text_primary"])
            else:
                btn.configure(fg_color="transparent", text_color=COLORS["text_secondary"])
        self._active = route
        self.on_navigate(route)
