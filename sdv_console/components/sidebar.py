"""Left sidebar navigation."""

import customtkinter as ctk

from sdv_console.config import APP_VERSION, COLORS, NAVIGATION_ITEMS, SIDEBAR_WIDTH


class Sidebar(ctk.CTkFrame):
    def __init__(self, master: ctk.CTk, on_select=None, **kwargs) -> None:
        super().__init__(
            master,
            width=SIDEBAR_WIDTH,
            fg_color=COLORS["bg_sidebar"],
            corner_radius=0,
            **kwargs,
        )
        self.grid_propagate(False)
        self._on_select = on_select
        self._nav_items: list[ctk.CTkButton] = []
        self._active = NAVIGATION_ITEMS[0]
        self._build_layout()

    def _build_layout(self) -> None:
        ctk.CTkLabel(
            self,
            text="MODULES",
            font=ctk.CTkFont(family="Segoe UI", size=11, weight="bold"),
            text_color=COLORS["text_muted"],
        ).pack(anchor="w", padx=20, pady=(16, 8))

        scroll = ctk.CTkScrollableFrame(self, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=4)

        for item in NAVIGATION_ITEMS:
            button = ctk.CTkButton(
                scroll,
                text=item,
                anchor="w",
                height=36,
                corner_radius=8,
                fg_color="transparent",
                hover_color=COLORS["bg_secondary"],
                text_color=COLORS["text_primary"],
                font=ctk.CTkFont(family="Segoe UI", size=12),
                command=lambda name=item: self.select(name),
            )
            button.pack(fill="x", padx=8, pady=1)
            self._nav_items.append(button)

        ctk.CTkLabel(
            self,
            text=f"v{APP_VERSION}",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=COLORS["text_muted"],
        ).pack(anchor="w", padx=20, pady=(4, 12))
        self._paint()

    def select(self, name: str) -> None:
        self._active = name
        self._paint()
        if self._on_select:
            self._on_select(name)

    def _paint(self) -> None:
        for button in self._nav_items:
            active = button.cget("text") == self._active
            button.configure(fg_color=COLORS["accent_muted"] if active else "transparent")
