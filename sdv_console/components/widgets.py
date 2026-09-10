"""Reusable UI building blocks. One definition of "what a stat card looks
like" used by every view — this is what keeps the console feeling like one
system instead of 13 differently-styled screens.
"""

from __future__ import annotations

import customtkinter as ctk

from sdv_console.config import COLORS, STATUS_COLORS


def status_color(status: str) -> str:
    return STATUS_COLORS.get(status, COLORS["text_muted"])


def format_uptime(started_iso: str) -> str:
    from datetime import datetime, timezone
    try:
        started = datetime.fromisoformat(started_iso)
    except ValueError:
        return "—"
    secs = int((datetime.now(timezone.utc) - started).total_seconds())
    h, rem = divmod(secs, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def section_title(parent, text: str) -> ctk.CTkLabel:
    return ctk.CTkLabel(parent, text=text, font=ctk.CTkFont(family="Segoe UI", size=18, weight="bold"), text_color=COLORS["text_primary"])


def caption(parent, text: str) -> ctk.CTkLabel:
    return ctk.CTkLabel(parent, text=text, font=ctk.CTkFont(size=11), text_color=COLORS["text_muted"], wraplength=900, justify="left", anchor="w")


class PanelCard(ctk.CTkFrame):
    """A titled card with a body frame — the base unit of every page."""

    def __init__(self, master, title: str, subtitle: str = "", **kwargs) -> None:
        super().__init__(master, fg_color=COLORS["bg_card"], corner_radius=12, border_width=1, border_color=COLORS["border"], **kwargs)
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=16, pady=(14, 4))
        ctk.CTkLabel(head, text=title.upper(), font=ctk.CTkFont(family="Segoe UI", size=12, weight="bold"), text_color=COLORS["accent"]).pack(anchor="w")
        if subtitle:
            ctk.CTkLabel(head, text=subtitle, font=ctk.CTkFont(size=10), text_color=COLORS["text_muted"]).pack(anchor="w")
        self.body = ctk.CTkFrame(self, fg_color="transparent")
        self.body.pack(fill="both", expand=True, padx=16, pady=(4, 14))


class MetricTile(ctk.CTkFrame):
    """Label + big value + unit — used inside PanelCard bodies."""

    def __init__(self, master, label: str, value: str, unit: str = "", **kwargs) -> None:
        super().__init__(master, fg_color=COLORS["bg_card_alt"], corner_radius=8, **kwargs)
        ctk.CTkLabel(self, text=label.upper(), font=ctk.CTkFont(size=9), text_color=COLORS["text_muted"]).pack(anchor="w", padx=10, pady=(8, 0))
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(anchor="w", padx=10, pady=(0, 8))
        self._value = ctk.CTkLabel(row, text=value, font=ctk.CTkFont(family="Consolas", size=18, weight="bold"), text_color=COLORS["text_primary"])
        self._value.pack(side="left")
        if unit:
            ctk.CTkLabel(row, text=f" {unit}", font=ctk.CTkFont(size=11), text_color=COLORS["text_muted"]).pack(side="left")

    def set(self, value: str, color: str | None = None) -> None:
        self._value.configure(text=value, text_color=color or COLORS["text_primary"])


class StatCard(ctk.CTkFrame):
    """Simple label/value pair for dense stat grids (Live Telemetry)."""

    def __init__(self, master, label: str, value: str, **kwargs) -> None:
        super().__init__(master, fg_color=COLORS["bg_card"], corner_radius=8, border_width=1, border_color=COLORS["border"], **kwargs)
        ctk.CTkLabel(self, text=label, font=ctk.CTkFont(size=10), text_color=COLORS["text_muted"]).pack(anchor="w", padx=10, pady=(8, 0))
        self._value = ctk.CTkLabel(self, text=value, font=ctk.CTkFont(family="Consolas", size=15, weight="bold"), text_color=COLORS["text_primary"])
        self._value.pack(anchor="w", padx=10, pady=(0, 8))

    def set_value(self, value: str, color: str | None = None) -> None:
        self._value.configure(text=value, text_color=color or COLORS["text_primary"])


class ECUTile(ctk.CTkFrame):
    """Full-detail ECU tile: name, status dot, health bar, firmware, last event."""

    def __init__(self, master, **kwargs) -> None:
        super().__init__(master, fg_color=COLORS["bg_card_alt"], corner_radius=10, **kwargs)
        top = ctk.CTkFrame(self, fg_color="transparent")
        top.pack(fill="x", padx=12, pady=(10, 2))
        self._name = ctk.CTkLabel(top, text="—", font=ctk.CTkFont(size=13, weight="bold"), text_color=COLORS["text_primary"])
        self._name.pack(side="left")
        self._status = ctk.CTkLabel(top, text="●", font=ctk.CTkFont(size=13), text_color=COLORS["offline"])
        self._status.pack(side="right")
        self._status_text = ctk.CTkLabel(self, text="OFFLINE", font=ctk.CTkFont(family="Consolas", size=10, weight="bold"), text_color=COLORS["offline"])
        self._status_text.pack(anchor="w", padx=12)
        self._bar = ctk.CTkProgressBar(self, height=6)
        self._bar.pack(fill="x", padx=12, pady=(6, 4))
        self._bar.set(0)
        self._meta = ctk.CTkLabel(self, text="", font=ctk.CTkFont(family="Consolas", size=9), text_color=COLORS["text_muted"], justify="left", anchor="w")
        self._meta.pack(anchor="w", padx=12, pady=(0, 10))

    def update_from(self, ecu: dict) -> None:
        color = status_color(ecu["status"])
        self._name.configure(text=ecu["name"])
        self._status.configure(text_color=color)
        self._status_text.configure(text=ecu["status"], text_color=color)
        self._bar.set(max(0, min(100, ecu["health"])) / 100)
        self._bar.configure(progress_color=color)
        self._meta.configure(text=f"FW {ecu['firmware']}   Task {ecu['task']}\nLast: {ecu['last_event']}")


class SparklineCanvas(ctk.CTkCanvas):
    def __init__(self, master, height: int = 40, color: str = "#3AA0FF", **kwargs) -> None:
        super().__init__(master, height=height, bg=COLORS["bg_card_alt"], highlightthickness=0, **kwargs)
        self.color = color

    def draw(self, points: list[float]) -> None:
        self.delete("all")
        w = max(self.winfo_width(), 40)
        h = int(self["height"])
        if len(points) < 2:
            return
        lo, hi = min(points), max(points)
        span = max(1e-6, hi - lo)
        coords = []
        for i, v in enumerate(points):
            x = i * w / (len(points) - 1)
            y = h - 4 - (v - lo) / span * (h - 8)
            coords.extend([x, y])
        self.create_line(*coords, fill=self.color, width=2, smooth=True)
