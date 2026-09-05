"""Live telemetry from Vehicle State (simulated until hardware ingest exists)."""

import customtkinter as ctk

from sdv_console.components.cards import StatCard
from sdv_console.components.widgets import caption, section_title
from sdv_console.config import COLORS
from sdv_console.platform import EngineeringPlatform


class TelemetryView(ctk.CTkScrollableFrame):
    def __init__(self, master, platform: EngineeringPlatform, **kwargs) -> None:
        super().__init__(master, fg_color=COLORS["bg_primary"], corner_radius=0, **kwargs)
        self.platform = platform
        self._cards: dict[str, StatCard] = {}
        self._canvas: ctk.CTkCanvas
        self._build()

    def _build(self) -> None:
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=24, pady=16)
        section_title(head, "Live Telemetry").pack(anchor="w")
        caption(
            head,
            "SIMULATION MODE generates these channels in software. They are not physical ADC readings until the STM32 "
            "publishes the same JSON keys over the ESP32 gateway.",
        ).pack(anchor="w")

        grid = ctk.CTkFrame(self, fg_color="transparent")
        grid.pack(fill="x", padx=24)
        keys = [
            ("engine_temp", "Engine temperature"),
            ("battery_voltage", "Battery voltage"),
            ("battery_current", "Battery current"),
            ("battery_power", "Battery power"),
            ("brake_status", "Brake status"),
            ("steering_status", "Steering status"),
            ("cabin_temp", "Cabin temperature"),
            ("adas_status", "ADAS status"),
            ("vehicle_state", "Vehicle state"),
            ("can_message_count", "CAN message count"),
        ]
        for i, (key, label) in enumerate(keys):
            card = StatCard(grid, label, "—")
            card.grid(row=i // 5, column=i % 5, sticky="nsew", padx=4, pady=4)
            grid.grid_columnconfigure(i % 5, weight=1)
            self._cards[key] = card

        section_title(self, "Battery voltage history").pack(anchor="w", padx=24, pady=(16, 8))
        self._canvas = ctk.CTkCanvas(self, bg=COLORS["bg_secondary"], highlightthickness=0, height=180)
        self._canvas.pack(fill="x", padx=24, pady=(0, 24))

    def refresh(self) -> None:
        snap = self.platform.snapshot()
        tel = snap["telemetry"]
        units = {
            "engine_temp": " °C",
            "battery_voltage": " V",
            "battery_current": " A",
            "battery_power": " W",
            "cabin_temp": " °C",
            "can_message_count": "",
        }
        for key, card in self._cards.items():
            value = tel.get(key, "—")
            suffix = units.get(key, "")
            card.set_value(f"{value}{suffix}" if value != "—" else "—")
        self._draw_history(snap["telemetry_history"].get("battery_voltage", []))

    def _draw_history(self, points: list[float]) -> None:
        c = self._canvas
        c.delete("all")
        w, h = max(c.winfo_width(), 100), 180
        if len(points) < 2:
            c.create_text(w // 2, h // 2, text="Collecting samples…", fill=COLORS["text_muted"])
            return
        lo, hi = min(points), max(points)
        span = max(0.2, hi - lo)
        xs = []
        ys = []
        for i, v in enumerate(points):
            x = 10 + i * (w - 20) / max(1, len(points) - 1)
            y = h - 16 - ((v - lo) / span) * (h - 32)
            xs.append(x)
            ys.append(y)
        coords = []
        for x, y in zip(xs, ys):
            coords.extend([x, y])
        c.create_line(*coords, fill=COLORS["accent_blueprint"], width=2)
        c.create_text(40, 14, text=f"{points[-1]:.2f} V", fill=COLORS["text_primary"], font=("Segoe UI", 11, "bold"))
