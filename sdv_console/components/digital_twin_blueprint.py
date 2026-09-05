"""2D digital twin — ECU health from VehicleStateManager, not hardcoded colors."""

from __future__ import annotations

from collections.abc import Callable

import customtkinter as ctk

from sdv_console.config import COLORS, STATUS_COLORS


class DigitalTwinBlueprint(ctk.CTkFrame):
    """Schematic of the vehicle software state. Driven by live ECU snapshots."""

    def __init__(
        self,
        master: ctk.CTkBaseClass,
        snapshot_fn: Callable[[], dict],
        **kwargs,
    ) -> None:
        super().__init__(
            master,
            fg_color=COLORS["bg_card"],
            border_color=COLORS["border"],
            border_width=1,
            corner_radius=12,
            **kwargs,
        )
        self._snapshot_fn = snapshot_fn
        self._subtitle_label: ctk.CTkLabel
        self._canvas: ctk.CTkCanvas
        self._build_layout()

    def _build_layout(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(16, 8))

        ctk.CTkLabel(
            header,
            text="Digital Twin",
            font=ctk.CTkFont(family="Segoe UI", size=14, weight="bold"),
            text_color=COLORS["text_primary"],
        ).pack(side="left")

        self._subtitle_label = ctk.CTkLabel(
            header,
            text="",
            font=ctk.CTkFont(family="Segoe UI", size=11),
            text_color=COLORS["text_muted"],
        )
        self._subtitle_label.pack(side="right")

        self._canvas = ctk.CTkCanvas(
            self,
            bg=COLORS["bg_secondary"],
            highlightthickness=0,
            height=280,
        )
        self._canvas.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        self._canvas.bind("<Configure>", lambda _e: self.refresh())

    def refresh(self) -> None:
        snap = self._snapshot_fn()
        mode = snap.get("connection_label", "")
        overall = snap.get("overall_health", "")
        self._subtitle_label.configure(text=f"{mode}  ·  vehicle {overall}")
        self._redraw_blueprint(snap.get("ecus", {}))

    def _draw(self, **kwargs) -> None:
        """Overrides CTkFrame's internal draw method safely."""
        super()._draw(**kwargs)
        if hasattr(self, "_snapshot_fn") and callable(self._snapshot_fn):
            snapshot = self._snapshot_fn()
            ecus = snapshot.get("ecus", {})
            self._redraw_blueprint(ecus)

    def _redraw_blueprint(self, ecus: dict) -> None:
        """Existing canvas/drawing logic for rendering ECU nodes."""
        canvas = self._canvas
        canvas.delete("all")
        width = canvas.winfo_width()
        height = canvas.winfo_height()
        if width <= 1 or height <= 1:
            return

        order = ["engine", "battery", "brake", "steering", "climate", "adas"]
        items = [ecus[k] for k in order if k in ecus]
        if not items:
            return

        line = COLORS["accent_blueprint"]
        center_x = width // 2
        vehicle_y = 28
        vehicle_h = 36
        vehicle_w = 160

        # Draw central "Vehicle" node box
        canvas.create_rectangle(
            center_x - vehicle_w // 2,
            vehicle_y,
            center_x + vehicle_w // 2,
            vehicle_y + vehicle_h,
            outline=line,
            width=2,
            fill=COLORS["bg_card"],
        )
        canvas.create_text(
            center_x,
            vehicle_y + vehicle_h // 2,
            text="Vehicle",
            fill=COLORS["text_primary"],
            font=("Segoe UI", 11, "bold"),
        )

        # Draw vertical trunk line from Vehicle box
        branch_y = vehicle_y + vehicle_h + 28
        canvas.create_line(center_x, vehicle_y + vehicle_h, center_x, branch_y, fill=line, width=2)

        # Calculate spacing and horizontal bus line for ECU nodes
        count = len(items)
        spacing = min(118, max(90, (width - 40) // count))
        total = spacing * (count - 1)
        start_x = center_x - total // 2
        canvas.create_line(start_x, branch_y, start_x + total, branch_y, fill=line, width=2)

        # Draw each individual ECU box and status text
        box_y = min(height - 48, branch_y + 70)
        for index, ecu in enumerate(items):
            x = start_x + index * spacing
            status = ecu.get("status", "OFFLINE")
            color = STATUS_COLORS.get(status, COLORS["offline"])

            # Connecting line to ECU box
            canvas.create_line(x, branch_y, x, box_y - 24, fill=color, width=2)

            # ECU status box
            canvas.create_rectangle(
                x - 48,
                box_y - 24,
                x + 48,
                box_y + 28,
                outline=color,
                width=2,
                fill=COLORS["bg_card"],
            )
            # ECU Name & Status Text
            canvas.create_text(
                x,
                box_y - 8,
                text=ecu["name"].replace(" ECU", ""),
                fill=COLORS["text_primary"],
                font=("Segoe UI", 9, "bold"),
            )
            canvas.create_text(
                x,
                box_y + 12,
                text=status,
                fill=color,
                font=("Segoe UI", 8, "bold"),
            )