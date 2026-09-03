"""Top header bar — vehicle name, connection mode, firmware from live state."""

import customtkinter as ctk

from sdv_console.config import APP_TITLE, COLORS
from sdv_console.platform import EngineeringPlatform


class HeaderBar(ctk.CTkFrame):
    def __init__(self, master: ctk.CTk, platform: EngineeringPlatform, **kwargs) -> None:
        super().__init__(
            master,
            height=72,
            fg_color=COLORS["bg_header"],
            corner_radius=0,
            **kwargs,
        )
        self._platform = platform
        self.grid_propagate(False)
        self._value_labels: dict[str, ctk.CTkLabel] = {}
        self._build_layout()
        self.refresh()

    def _build_layout(self) -> None:
        self.grid_columnconfigure(0, weight=1)

        title_frame = ctk.CTkFrame(self, fg_color="transparent")
        title_frame.grid(row=0, column=0, sticky="w", padx=24, pady=16)

        ctk.CTkLabel(
            title_frame,
            text=APP_TITLE,
            font=ctk.CTkFont(family="Segoe UI", size=20, weight="bold"),
            text_color=COLORS["text_primary"],
        ).pack(anchor="w")
        ctk.CTkLabel(
            title_frame,
            text="OTA attestation workflow · cloud-assisted digital twin · real-time diagnostics",
            font=ctk.CTkFont(family="Segoe UI", size=12),
            text_color=COLORS["text_muted"],
        ).pack(anchor="w", pady=(2, 0))

        status_frame = ctk.CTkFrame(self, fg_color="transparent")
        status_frame.grid(row=0, column=1, sticky="e", padx=24, pady=16)
        for key, label in (
            ("vehicle", "Vehicle"),
            ("connection", "Connection"),
            ("firmware", "Firmware"),
            ("health", "Health"),
        ):
            self._value_labels[key] = self._add_status_item(status_frame, label, "—")

    def _add_status_item(self, parent, label, value) -> ctk.CTkLabel:
        item = ctk.CTkFrame(parent, fg_color="transparent")
        item.pack(side="left", padx=(0, 24))
        ctk.CTkLabel(item, text=label, font=ctk.CTkFont(size=11), text_color=COLORS["text_muted"]).pack(anchor="e")
        value_label = ctk.CTkLabel(
            item,
            text=value,
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=COLORS["text_primary"],
        )
        value_label.pack(anchor="e", pady=(2, 0))
        return value_label

    def refresh(self) -> None:
        snap = self._platform.snapshot()
        self._value_labels["vehicle"].configure(text=snap["vehicle_name"])
        conn = snap["connection_label"]
        conn_color = COLORS["warning"] if conn == "SIMULATION MODE" else (
            COLORS["success"] if conn == "CONNECTED" else COLORS["error"]
        )
        self._value_labels["connection"].configure(text=conn, text_color=conn_color)
        self._value_labels["firmware"].configure(text=snap["firmware"])
        health = snap["overall_health"]
        from sdv_console.config import STATUS_COLORS

        self._value_labels["health"].configure(text=health, text_color=STATUS_COLORS.get(health, COLORS["text_primary"]))
