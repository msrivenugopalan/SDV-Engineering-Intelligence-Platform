"""Live Telemetry (architecture doc §8). Reads the same telemetry_history
rolling buffers Central State exposes — no separate simulation here.
"""

from __future__ import annotations

import customtkinter as ctk

from sdv_console.components.widgets import StatCard, caption, section_title
from sdv_console.config import COLORS

CHART_METRICS = {
    "Battery voltage": ("battery_voltage", " V", 2, COLORS["mono"]),
    "Vehicle speed": ("vehicle_speed", " km/h", 1, COLORS["accent"]),
    "Battery SoC": ("battery_soc", " %", 1, COLORS["success"]),
    "Motor temperature": ("engine_temp", " °C", 1, COLORS["warning"]),
    "Battery current": ("battery_current", " A", 2, COLORS["intelligence"]),
}


class TelemetryView(ctk.CTkScrollableFrame):
    def __init__(self, master, platform, **kwargs) -> None:
        super().__init__(master, fg_color=COLORS["bg_primary"], corner_radius=0, **kwargs)
        self.platform = platform
        self._cards: dict[str, StatCard] = {}
        self._chart_choice = ctk.StringVar(value="Battery voltage")
        self._build()

    def _build(self) -> None:
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=24, pady=16)
        section_title(head, "Live Telemetry").pack(anchor="w")
        caption(head, "Sensor → ECU → STM32 → CAN/UART → ESP32 → REST/MQTT → Central State → charts (architecture doc §8). "
                       "SIMULATION MODE generates these values in software until the STM32 publishes the same fields.").pack(anchor="w")

        grid = ctk.CTkFrame(self, fg_color="transparent")
        grid.pack(fill="x", padx=24)
        keys = [
            ("vehicle_speed", "Vehicle speed"), ("battery_soc", "Battery SoC"), ("estimated_range", "Estimated range"),
            ("engine_temp", "Motor temperature"), ("battery_voltage", "Battery voltage"), ("battery_current", "Battery current"),
            ("battery_power", "Battery power"), ("cabin_temp", "Cabin temperature"), ("brake_status", "Brake status"),
            ("steering_status", "Steering status"), ("adas_status", "ADAS status"), ("vehicle_state", "Vehicle state"),
        ]
        for i, (key, label) in enumerate(keys):
            card = StatCard(grid, label, "—")
            card.grid(row=i // 4, column=i % 4, sticky="nsew", padx=4, pady=4)
            grid.grid_columnconfigure(i % 4, weight=1)
            self._cards[key] = card

        chart_head = ctk.CTkFrame(self, fg_color="transparent")
        chart_head.pack(fill="x", padx=24, pady=(20, 8))
        section_title(chart_head, "History").pack(side="left")
        ctk.CTkOptionMenu(chart_head, variable=self._chart_choice, values=list(CHART_METRICS.keys()), width=190,
                           fg_color=COLORS["bg_card_alt"], button_color=COLORS["accent_muted"], command=lambda _v: self.refresh()).pack(side="right")

        self._canvas = ctk.CTkCanvas(self, bg=COLORS["bg_secondary"], highlightthickness=0, height=260)
        self._canvas.pack(fill="x", padx=24, pady=(0, 24))

    def refresh(self) -> None:
        snap = self.platform.snapshot()
        tel = snap["telemetry"]
        units = {"vehicle_speed": " km/h", "battery_soc": " %", "estimated_range": " km", "engine_temp": " °C",
                 "battery_voltage": " V", "battery_current": " A", "battery_power": " W", "cabin_temp": " °C"}
        for key, card in self._cards.items():
            v = tel.get(key, "—")
            card.set_value(f"{v}{units.get(key, '')}" if v != "—" else "—")

        label = self._chart_choice.get()
        key, unit, dp, color = CHART_METRICS.get(label, CHART_METRICS["Battery voltage"])
        self._draw_chart(snap["telemetry_history"].get(key, []), label=label, unit=unit, dp=dp, color=color)

    def _draw_chart(self, points: list[float], *, label: str, unit: str, dp: int, color: str) -> None:
        c = self._canvas
        c.delete("all")
        w = max(c.winfo_width(), 200)
        h = 260
        pad_l, pad_r, pad_t, pad_b = 54, 16, 20, 28
        plot_w, plot_h = max(1, w - pad_l - pad_r), max(1, h - pad_t - pad_b)
        c.create_text(pad_l, 10, text=label, anchor="w", fill=COLORS["text_primary"], font=("Segoe UI", 11, "bold"))

        if len(points) < 2:
            c.create_text(w // 2, h // 2, text="Collecting samples…", fill=COLORS["text_muted"])
            return

        lo, hi = min(points), max(points)
        span = max(1e-6, hi - lo)
        pad_span = max(span * 0.12, 0.05)
        axis_lo, axis_hi = lo - pad_span, hi + pad_span

        grid_color = COLORS["border"]
        for i in range(5):
            frac = i / 4
            y = pad_t + plot_h * (1 - frac)
            value = axis_lo + (axis_hi - axis_lo) * frac
            c.create_line(pad_l, y, pad_l + plot_w, y, fill=grid_color, width=1)
            c.create_text(pad_l - 8, y, text=f"{value:.{dp}f}", anchor="e", fill=COLORS["text_muted"], font=("Consolas", 9))

        c.create_line(pad_l, pad_t, pad_l, pad_t + plot_h, fill=grid_color, width=1)
        c.create_line(pad_l, pad_t + plot_h, pad_l + plot_w, pad_t + plot_h, fill=grid_color, width=1)
        n = len(points)
        for i in range(5):
            frac = i / 4
            x = pad_l + plot_w * frac
            secs_ago = int((1 - frac) * n * 0.25)
            c.create_text(x, pad_t + plot_h + 8, text=f"-{secs_ago}s", anchor="n", fill=COLORS["text_muted"], font=("Consolas", 8))

        coords = []
        for i, v in enumerate(points):
            x = pad_l + i * plot_w / max(1, n - 1)
            y = pad_t + plot_h * (1 - (v - axis_lo) / (axis_hi - axis_lo))
            coords.extend([x, y])
        c.create_line(*coords, fill=color, width=2, smooth=True)
        last_x, last_y = coords[-2], coords[-1]
        c.create_oval(last_x - 4, last_y - 4, last_x + 4, last_y + 4, fill=color, outline=COLORS["bg_secondary"], width=2)
        c.create_text(pad_l + plot_w - 4, pad_t + 4, text=f"{points[-1]:.{dp}f}{unit}", anchor="ne", fill=COLORS["text_primary"], font=("Consolas", 12, "bold"))
