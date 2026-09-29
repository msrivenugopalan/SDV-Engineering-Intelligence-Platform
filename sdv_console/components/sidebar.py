from __future__ import annotations

from collections.abc import Callable

import customtkinter as ctk

from sdv_console.config import APP_VERSION, COLORS, NAVIGATION

SIDEBAR_WIDTH = 300


class Sidebar(ctk.CTkScrollableFrame):
    def __init__(self, master, on_navigate: Callable[[str], None], **kwargs) -> None:
        super().__init__(master, fg_color=COLORS["bg_secondary"], corner_radius=0, width=SIDEBAR_WIDTH, **kwargs)
        self.on_navigate = on_navigate
        self._buttons: dict[str, ctk.CTkButton] = {}
        self._active = "overview"

        self.configure(
            scrollbar_fg_color=COLORS["bg_secondary"],
            scrollbar_button_color=COLORS["offline"],
            scrollbar_button_hover_color=COLORS["accent_muted"],
        )
        brand = ctk.CTkFrame(self, fg_color="transparent")
        brand.pack(fill="x", padx=16, pady=(18, 10))
        ctk.CTkLabel(brand, text="SDV ENGINEERING CONSOLE", font=ctk.CTkFont(family="Segoe UI", size=17, weight="bold"), text_color=COLORS["text_primary"]).pack(anchor="w")
        ctk.CTkLabel(brand, text="Intelligent Software-Defined Vehicle\nEngineering Platform", font=ctk.CTkFont(size=10), text_color=COLORS["text_muted"], justify="left").pack(anchor="w", pady=(4, 0))
        divider = ctk.CTkFrame(self, height=1, fg_color=COLORS["border"])
        divider.pack(fill="x", padx=16, pady=(2, 4))
        ctk.CTkLabel(self, text="NAVIGATION", font=ctk.CTkFont(size=10, weight="bold"), text_color=COLORS["text_muted"]).pack(anchor="w", padx=16, pady=(14, 8))

        for section, items in NAVIGATION:
            ctk.CTkLabel(self, text=section, font=ctk.CTkFont(size=10, weight="bold"), text_color=COLORS["accent"]).pack(anchor="w", padx=16, pady=(18, 6))
            for display, icon, route in items:
                btn = ctk.CTkButton(
                    self, text=f"  {icon}   {display}", anchor="w", height=40, corner_radius=6,
                    fg_color="transparent", hover_color=COLORS["bg_card_alt"],
                    text_color=COLORS["text_secondary"], font=ctk.CTkFont(size=13),
                    command=lambda r=route: self._select(r),
                )
                btn.pack(fill="x", padx=12, pady=2)
                self._buttons[route] = btn

        ctk.CTkLabel(self, text=f"Console v{APP_VERSION}", font=ctk.CTkFont(size=9), text_color=COLORS["text_muted"]).pack(anchor="w", padx=16, pady=(24, 2))
        ctk.CTkLabel(self, text="SIMULATION · HARDWARE READY", font=ctk.CTkFont(size=9, weight="bold"), text_color=COLORS["text_muted"]).pack(anchor="w", padx=16, pady=(0, 14))

        self._select(self._active)
        

    def _select(self, route: str) -> None:
        for r, btn in self._buttons.items():
            if r == route:
                btn.configure(fg_color=COLORS["accent_muted"], text_color=COLORS["text_primary"])
            else:
                btn.configure(fg_color="transparent", text_color=COLORS["text_secondary"])
        self._active = route
        self.on_navigate(route)
