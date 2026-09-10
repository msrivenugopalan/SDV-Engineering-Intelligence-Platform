"""Digital Twin (architecture doc §9) — a live visual of Central State, not
just a picture of a car. Every node color/label comes straight from
`platform.snapshot()["ecus"]`.

Perf: the static scene (grid, hull, roof, wheels) is drawn once per canvas
size and cached; refresh() only recolors/retexts the small set of items
that can actually change (ECU node dots/links/labels + the hub status),
via itemconfig instead of delete+recreate. That's what keeps this smooth
at 4 refreshes/second even embedded in two places at once (Overview +
the full Digital Twin page).
"""

from __future__ import annotations

from collections.abc import Callable

import customtkinter as ctk

from sdv_console.components.widgets import status_color
from sdv_console.config import COLORS

# id, label, (relative x, relative y) around the vehicle hull
LAYOUT = [
    ("engine", "Motor", (0, -1)),
    ("battery", "Battery", (-1, 0.3)),
    ("brake", "Brake", (-0.6, -0.6)),
    ("steering", "Steering", (0.6, -0.6)),
    ("climate", "Climate", (0, 1)),
    ("adas", "ADAS", (1, 0.3)),
]


class DigitalTwin(ctk.CTkFrame):
    def __init__(self, master, snapshot_fn: Callable[[], dict], compact: bool = False, **kwargs) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)
        self._snapshot_fn = snapshot_fn
        self._compact = compact
        self._canvas = ctk.CTkCanvas(self, bg=COLORS["bg_secondary"], highlightthickness=0)
        self._canvas.pack(fill="both", expand=True)
        self._canvas.bind("<Configure>", lambda _e: self.refresh())

        self._static_size: tuple[int, int] | None = None
        self._hub_items: dict[str, int] = {}
        self._node_items: dict[str, dict[str, int]] = {}
        self._stamp = None

    def refresh(self) -> None:
        snap = self._snapshot_fn()
        canvas = self._canvas
        size = (canvas.winfo_width(), canvas.winfo_height())
        if size[0] <= 1 or size[1] <= 1:
            return

        ecus = snap.get("ecus", {})
        ecu_stamp = tuple(sorted((k, e["status"]) for k, e in ecus.items()))
        stamp = (size, snap.get("overall_health"), snap.get("firmware"), ecu_stamp)
        if stamp == self._stamp and size == self._static_size:
            return

        if size != self._static_size or not self._node_items:
            self._full_redraw(snap, size)
            self._static_size = size
        else:
            self._update_dynamic(snap)
        self._stamp = stamp

    def _full_redraw(self, snap: dict, size: tuple[int, int]) -> None:
        canvas = self._canvas
        canvas.delete("all")
        w, h = size
        cx, cy = w / 2, h / 2 - (6 if not self._compact else 0)
        scale = min(w, h) * (0.16 if not self._compact else 0.14)

        # Ground grid
        grid_color = COLORS["border"]
        for i in range(-3, 4):
            canvas.create_line(0, cy + i * scale * 0.5, w, cy + i * scale * 0.5, fill=grid_color, width=1)

        # Vehicle hull (simple diamond outline — isometric-ish silhouette)
        hull_color = status_color(snap.get("overall_health", "OFFLINE"))
        pts = [cx, cy - scale, cx + scale * 1.6, cy, cx, cy + scale, cx - scale * 1.6, cy]
        canvas.create_polygon(*pts, outline=hull_color, fill="", width=2)

        # Hub label
        self._hub_items = {
            "title": canvas.create_text(cx, cy - 14, text="VEHICLE", fill=COLORS["text_primary"], font=("Segoe UI", 9, "bold")),
            "status": canvas.create_text(cx, cy + 2, text=snap.get("overall_health", "—"), fill=hull_color, font=("Consolas", 10, "bold")),
        }

        self._node_items = {}
        for ecu_id, label, (rx, ry) in LAYOUT:
            ecu = snap["ecus"].get(ecu_id)
            if not ecu:
                continue
            color = status_color(ecu["status"])
            px, py = cx + rx * scale * 1.7, cy + ry * scale * 1.5
            link = canvas.create_line(cx, cy, px, py, fill=color, width=1, dash=(3, 2))
            dot = canvas.create_oval(px - 6, py - 6, px + 6, py + 6, fill=color, outline=COLORS["bg_secondary"], width=2)
            name_txt = canvas.create_text(px, py + 16, text=label, fill=COLORS["text_primary"], font=("Segoe UI", 8, "bold"))
            status_txt = canvas.create_text(px, py + 28, text=ecu["status"], fill=color, font=("Consolas", 7, "bold"))
            self._node_items[ecu_id] = {"link": link, "dot": dot, "status_txt": status_txt}

        if not self._compact:
            canvas.create_text(8, h - 10, text=f"FW {snap.get('firmware', '—')}  ·  isometric twin, live ECU state", anchor="w", fill=COLORS["text_muted"], font=("Segoe UI", 8))

    def _update_dynamic(self, snap: dict) -> None:
        canvas = self._canvas
        hull_color = status_color(snap.get("overall_health", "OFFLINE"))
        if self._hub_items:
            canvas.itemconfig(self._hub_items["status"], text=snap.get("overall_health", "—"), fill=hull_color)
        for ecu_id, _label, _pos in LAYOUT:
            items = self._node_items.get(ecu_id)
            ecu = snap["ecus"].get(ecu_id)
            if not items or not ecu:
                continue
            color = status_color(ecu["status"])
            canvas.itemconfig(items["link"], fill=color)
            canvas.itemconfig(items["dot"], fill=color)
            canvas.itemconfig(items["status_txt"], text=ecu["status"], fill=color)
