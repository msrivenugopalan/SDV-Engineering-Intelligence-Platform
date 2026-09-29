"""Digital Twin — live visual of Central State (architecture doc §9).

Every node color, firmware string, telemetry value, fault, recovery state,
CAN rate, and mode badge is read from `platform.snapshot()`. This module
owns no vehicle state of its own.

Rendering is Tk Canvas (no extra 3D stack): static geometry is rebuilt on
resize / view-mode / zoom; refresh() then itemconfig's the live items.
"""

from __future__ import annotations

import math
import time
from collections.abc import Callable

import customtkinter as ctk

from sdv_console.components.widgets import status_color, status_mark
from sdv_console.config import COLORS, ECU_CATALOG

# Visual-only domain tags. These are grouping labels, NOT extra ECUs.
# attach / card coordinates live in a 1000×560 design space.
NODE_LAYOUT = {
    "adas":     {"attach": (390, 148), "card": (390, 42),  "domain": "ADAS",       "side": "top"},
    "climate":  {"attach": (560, 175), "card": (780, 70),  "domain": "CABIN",      "side": "right"},
    "steering": {"attach": (340, 230), "card": (70, 70),   "domain": "CHASSIS",    "side": "left"},
    "engine":   {"attach": (250, 318), "card": (70, 455),  "domain": "POWERTRAIN", "side": "left"},
    "battery":  {"attach": (520, 348), "card": (860, 455), "domain": "ENERGY",     "side": "right"},
    "brake":    {"attach": (690, 410), "card": (820, 530), "domain": "CHASSIS",    "side": "bottom"},
}

# Telemetry fields that actually exist in VehicleState.NOMINAL_TELEMETRY.
ECU_TELEMETRY = {
    "engine": [
        ("engine_temp", "Temperature", "°C"),
        ("vehicle_speed", "Vehicle speed", "km/h"),
    ],
    "battery": [
        ("battery_voltage", "Voltage", "V"),
        ("battery_current", "Current", "A"),
        ("battery_power", "Power", "W"),
        ("battery_soc", "SoC", "%"),
        ("estimated_range", "Range", "km"),
    ],
    "brake": [
        ("brake_status", "Brake status", ""),
    ],
    "steering": [
        ("steering_status", "Steering status", ""),
    ],
    "climate": [
        ("cabin_temp", "Cabin temp", "°C"),
    ],
    "adas": [
        ("adas_status", "ADAS status", ""),
        ("vehicle_state", "Vehicle state", ""),
    ],
}

WIRE = "#4EC3FF"
WIRE_SOFT = "#1E5A8A"
BODY_FILL = "#0A1A2C"
WINDOW_FILL = "#071525"
MOTOR_ORANGE = "#FF7A2E"
MOTOR_CORE = "#FFC078"
BATT_GREEN = "#2ECC71"
BATT_CORE = "#7DFFB2"
GRID = "#14344F"
HUD_BG = "#07111C"
CAN_ID = "__can__"
VEHICLE_ID = "__vehicle__"


def _hex_lerp(a: str, b: str, t: float) -> str:
    t = max(0.0, min(1.0, t))
    def ch(h, i):
        return int(h[i:i + 2], 16)
    r = int(ch(a, 1) + (ch(b, 1) - ch(a, 1)) * t)
    g = int(ch(a, 3) + (ch(b, 3) - ch(a, 3)) * t)
    bl = int(ch(a, 5) + (ch(b, 5) - ch(a, 5)) * t)
    return f"#{r:02X}{g:02X}{bl:02X}"


def _heat_color(temp: float, lo: float, hi: float) -> str:
    span = max(1.0, hi - lo)
    t = (float(temp) - lo) / span
    if t < 0.5:
        return _hex_lerp("#1A6BFF", "#F5A623", t * 2)
    return _hex_lerp("#F5A623", "#E74C3C", (t - 0.5) * 2)


def _fmt(value, unit: str = "") -> str:
    if value is None:
        return "—"
    if isinstance(value, float):
        text = f"{value:.1f}" if abs(value) >= 10 else f"{value:.2f}"
    else:
        text = str(value)
    return f"{text} {unit}".strip()


class DigitalTwin(ctk.CTkFrame):
    def __init__(
        self,
        master,
        snapshot_fn: Callable[[], dict],
        compact: bool = False,
        on_select: Callable[[str | None], None] | None = None,
        **kwargs,
    ) -> None:
        super().__init__(master, fg_color="transparent", **kwargs)
        self._snapshot_fn = snapshot_fn
        self._compact = compact
        self._on_select = on_select
        self._view_mode = "engineering"
        self._zoom = 1.0
        self.selected_id: str | None = None

        bg = HUD_BG if not compact else COLORS["bg_secondary"]
        self._canvas = ctk.CTkCanvas(self, bg=bg, highlightthickness=0)
        self._canvas.pack(fill="both", expand=True)
        self._canvas.bind("<Configure>", lambda _e: self.refresh())
        self._canvas.bind("<Button-1>", self._on_click)
        self._canvas.bind("<Motion>", self._on_motion)
        self._canvas.bind("<Leave>", lambda _e: self._hide_tip())

        self._static_size: tuple[int, int] | None = None
        self._hub_items: dict[str, int] = {}
        self._node_items: dict[str, dict] = {}
        self._hits: list[tuple[str, float, float, float, float]] = []
        self._stamp = None
        self._last_snap: dict = {}
        self._xf = (0.0, 0.0, 1.0)
        self._packet_t = 0.0
        self._anim_job: str | None = None
        self._tip_bg = None
        self._tip_txt = None

        self.bind("<Destroy>", self._on_destroy)
        if not compact:
            self._arm_anim()

    # -------------------------------------------------------------- API --

    def set_view_mode(self, mode: str) -> None:
        if mode == self._view_mode:
            return
        self._view_mode = mode
        self._stamp = None
        self._static_size = None
        self.refresh()

    def set_zoom(self, delta: float) -> None:
        self._zoom = max(0.72, min(1.35, self._zoom + delta))
        self._stamp = None
        self._static_size = None
        self.refresh()

    def reset_view(self) -> None:
        self._zoom = 1.0
        self.selected_id = None
        self._stamp = None
        self._static_size = None
        if self._on_select:
            self._on_select(None)
        self.refresh()

    # ----------------------------------------------------------- refresh --

    def refresh(self) -> None:
        snap = self._snapshot_fn()
        self._last_snap = snap
        canvas = self._canvas
        size = (canvas.winfo_width(), canvas.winfo_height())
        if size[0] <= 1 or size[1] <= 1:
            return

        recovering = any(e.get("status") == "RECOVERING" for e in snap.get("ecus", {}).values())
        stamp = self._make_stamp(snap, size, recovering)
        if stamp == self._stamp and size == self._static_size:
            return

        prev = self._stamp
        geometry_changed = (
            prev is None
            or size != self._static_size
            or not self._node_items
            or stamp[0:4] != prev[0:4]
            or self._view_mode in {"thermal", "power", "fault"}
        )
        if geometry_changed:
            self._full_redraw(snap, size)
            self._static_size = size
        else:
            self._update_dynamic(snap)
        self._stamp = stamp

    def _make_stamp(self, snap: dict, size: tuple[int, int], recovering: bool) -> tuple:
        ecus = snap.get("ecus", {})
        tel = snap.get("telemetry", {})
        can = snap.get("can", {})
        ota = snap.get("ota", {})
        rec = snap.get("recovery", {})
        ecu_stamp = tuple(sorted(
            (k, e.get("status"), e.get("health"), e.get("firmware"), e.get("fault_id"), e.get("recovery_state"))
            for k, e in ecus.items()
        ))
        pulse = int(time.time() * 4) if recovering else 0
        return (
            self._view_mode,
            self._zoom,
            self.selected_id,
            size,
            snap.get("overall_health"),
            snap.get("firmware"),
            snap.get("mode"),
            ota.get("status"),
            ota.get("progress"),
            rec.get("status"),
            rec.get("ecu"),
            can.get("bus_state"),
            can.get("messages_per_sec"),
            tel.get("engine_temp"),
            tel.get("cabin_temp"),
            tel.get("battery_voltage"),
            tel.get("battery_current"),
            tel.get("battery_power"),
            tel.get("battery_soc"),
            tel.get("vehicle_speed"),
            tel.get("brake_status"),
            tel.get("steering_status"),
            tel.get("adas_status"),
            bool(snap.get("services", {}).get("stm32")),
            ecu_stamp,
            pulse,
        )

    # ------------------------------------------------------------ draw --

    def _full_redraw(self, snap: dict, size: tuple[int, int]) -> None:
        canvas = self._canvas
        canvas.delete("all")
        self._hits = []
        self._node_items = {}
        self._hub_items = {}
        w, h = size
        self._xf = self._fit(w, h)

        self._draw_grid(w, h)
        if self._view_mode == "system":
            self._draw_system_view(snap, w, h)
        else:
            self._draw_vehicle(snap)
            if self._view_mode == "thermal":
                self._draw_thermal(snap)
            elif self._view_mode == "power":
                self._draw_power(snap)
            self._draw_nodes(snap)
            if self._view_mode == "fault":
                self._draw_fault_banner(snap)
        self._draw_hud(snap, w, h)
        self._tip_bg = canvas.create_rectangle(0, 0, 0, 0, fill=COLORS["bg_card"], outline=COLORS["accent"], width=1, state="hidden")
        self._tip_txt = canvas.create_text(0, 0, text="", fill=COLORS["text_primary"], font=("Segoe UI", 8), state="hidden", anchor="nw")

    def _fit(self, w: int, h: int) -> tuple[float, float, float]:
        margin_x = 18 if self._compact else 28
        margin_y = 12 if self._compact else 36
        usable_w = max(40, w - 2 * margin_x)
        usable_h = max(40, h - 2 * margin_y - (18 if self._compact else 8))
        s = min(usable_w / 1000.0, usable_h / 560.0) * self._zoom
        ox = (w - 1000 * s) / 2
        oy = (h - 560 * s) / 2 + (8 if not self._compact else 0)
        return ox, oy, s

    def _xy(self, x: float, y: float) -> tuple[float, float]:
        ox, oy, s = self._xf
        return ox + x * s, oy + y * s

    def _poly(self, pts: list[tuple[float, float]], **kw) -> int:
        flat = []
        for x, y in pts:
            px, py = self._xy(x, y)
            flat.extend((px, py))
        return self._canvas.create_polygon(*flat, **kw)

    def _line(self, pts: list[tuple[float, float]], **kw) -> int:
        flat = []
        for x, y in pts:
            px, py = self._xy(x, y)
            flat.extend((px, py))
        return self._canvas.create_line(*flat, **kw)

    def _oval(self, x: float, y: float, rx: float, ry: float, **kw) -> int:
        x1, y1 = self._xy(x - rx, y - ry)
        x2, y2 = self._xy(x + rx, y + ry)
        return self._canvas.create_oval(x1, y1, x2, y2, **kw)

    def _draw_grid(self, w: int, h: int) -> None:
        canvas = self._canvas
        ox, oy, s = self._xf
        horizon = oy + 430 * s
        # perspective floor
        for i in range(0, 14):
            yy = horizon + i * i * 1.6
            if yy > h:
                break
            shade = _hex_lerp(HUD_BG, GRID, min(1.0, 0.15 + i * 0.04))
            canvas.create_line(0, yy, w, yy, fill=shade, width=1)
        vanish_x = ox + 500 * s
        vanish_y = oy + 210 * s
        for i in range(-10, 11):
            x = vanish_x + i * 70 * s
            canvas.create_line(x, h, vanish_x, vanish_y, fill=GRID, width=1)
        # faint vignette corners
        canvas.create_rectangle(0, 0, w, 2, fill=COLORS["accent"], outline="")

    def _draw_vehicle(self, snap: dict) -> None:
        health = snap.get("overall_health", "OFFLINE")
        body_line = WIRE if health != "FAULT" else COLORS["error"]
        if health == "WARNING":
            body_line = COLORS["warning"]
        if health == "OFFLINE":
            body_line = COLORS["offline"]

        # Shadow / ground plane
        self._oval(480, 445, 310, 28, fill="#061018", outline="")

        # Far body (depth)
        far = [(236, 292), (248, 248), (338, 168), (640, 164), (728, 238), (790, 288), (792, 348), (236, 318)]
        self._poly(far, fill="#0C2236", outline=WIRE_SOFT, width=1)

        # Near body fill
        body = [
            (198, 338), (210, 292), (292, 236), (368, 168),
            (640, 168), (718, 236), (768, 292), (778, 338),
            (772, 382), (206, 382),
        ]
        self._poly(body, fill=BODY_FILL, outline=body_line, width=2)

        # Belt line / 3D thickness
        self._line([(210, 292), (248, 248), (338, 168), (368, 168)], fill=WIRE_SOFT, width=1)
        self._line([(640, 168), (678, 164), (728, 238), (768, 292)], fill=WIRE_SOFT, width=1)
        self._line([(778, 338), (792, 288)], fill=WIRE_SOFT, width=1)

        # Windows
        windshield = [(300, 246), (370, 178), (455, 178), (430, 246)]
        self._poly(windshield, fill=WINDOW_FILL, outline=WIRE, width=1)
        roof_glass = [(462, 178), (632, 178), (700, 244), (438, 244)]
        self._poly(roof_glass, fill=WINDOW_FILL, outline=WIRE, width=1)
        self._line([(430, 246), (438, 244)], fill=WIRE, width=1)
        # door cuts
        self._line([(430, 246), (430, 378)], fill=WIRE_SOFT, width=1)
        self._line([(560, 244), (560, 378)], fill=WIRE_SOFT, width=1)
        self._line([(206, 338), (772, 338)], fill=WIRE_SOFT, width=1)


        # Technical body scaffold. These fine lines make the body read as a
        # transparent engineering model while keeping the silhouette restrained.
        for x in (350, 465, 585, 680):
            self._line([(x, 183), (x - 18, 248), (x - 14, 336), (x - 6, 376)], fill="#164D76", width=1)
        self._line([(330, 198), (665, 198)], fill="#17486D", width=1, dash=(3, 3))
        self._line([(286, 266), (704, 266)], fill="#17486D", width=1, dash=(3, 3))
        self._line([(235, 300), (746, 300)], fill="#123C5D", width=1)
        self._line([(328, 318), (660, 318)], fill="#164D76", width=1, dash=(4, 3))
        # Cabin cross-members and a compact instrument-plane cue.
        self._line([(375, 190), (420, 300)], fill="#1A527C", width=1)
        self._line([(628, 190), (575, 300)], fill="#1A527C", width=1)
        self._line([(442, 262), (548, 262)], fill="#235E89", width=1)
        self._line([(456, 271), (535, 271)], fill="#164D76", width=1)
        # Headlamp / tail
        self._poly([(198, 328), (218, 318), (218, 348), (200, 352)], fill="#8FD4FF", outline=WIRE, width=1)
        self._oval(208, 334, 18, 10, fill="", outline="#8FD4FF", width=1)
        self._poly([(760, 322), (778, 318), (778, 350), (760, 352)], fill="#E74C3C", outline="#C0392B", width=1)

        # Mirror / A-pillar
        self._poly([(292, 246), (278, 238), (286, 228), (304, 236)], fill=BODY_FILL, outline=WIRE, width=1)
        self._line([(368, 168), (300, 246), (206, 338)], fill=WIRE_SOFT, width=1)
        self._line([(640, 168), (718, 236), (778, 338)], fill=WIRE_SOFT, width=1)

        # Fender arches
        self._line([(232, 382), (248, 360), (308, 360), (328, 382)], fill=WIRE, width=1)
        self._line([(642, 382), (658, 360), (718, 360), (742, 382)], fill=WIRE, width=1)

        # Motor / powertrain volume (front)
        motor_col = MOTOR_ORANGE
        if snap.get("ecus", {}).get("engine", {}).get("status") == "FAULT":
            motor_col = COLORS["error"]
        elif snap.get("ecus", {}).get("engine", {}).get("status") == "RECOVERING":
            motor_col = COLORS["warning"]
        self._poly([(218, 300), (318, 292), (322, 358), (220, 364)], fill="#2A1408", outline=motor_col, width=2)
        self._poly([(228, 308), (308, 302), (310, 348), (230, 352)], fill=motor_col, outline=MOTOR_CORE, width=1)
        if not self._compact:
            mx, my = self._xy(268, 328)
            self._canvas.create_text(mx, my, text="MOTOR", fill="#1A0A00", font=("Segoe UI", 7, "bold"))

        # Battery pack (floor)
        batt_col = BATT_GREEN
        if snap.get("ecus", {}).get("battery", {}).get("status") == "FAULT":
            batt_col = COLORS["error"]
        elif snap.get("ecus", {}).get("battery", {}).get("status") == "RECOVERING":
            batt_col = COLORS["warning"]
        self._poly([(350, 328), (655, 328), (658, 368), (348, 368)], fill="#062416", outline=batt_col, width=2)
        self._poly([(360, 334), (645, 334), (646, 360), (359, 360)], fill=batt_col, outline=BATT_CORE, width=1)
        self._line([(400, 334), (400, 360)], fill="#0B3D22", width=1)
        self._line([(500, 334), (500, 360)], fill="#0B3D22", width=1)
        self._line([(600, 334), (600, 360)], fill="#0B3D22", width=1)
        if not self._compact:
            bx, by = self._xy(500, 347)
            self._canvas.create_text(bx, by, text="BATTERY PACK", fill="#062416", font=("Segoe UI", 7, "bold"))

        # Wheels
        self._draw_wheel(278, 400, 36, far=False)
        self._draw_wheel(688, 400, 36, far=False)
        self._draw_wheel(318, 372, 28, far=True)
        self._draw_wheel(728, 372, 28, far=True)

        # Cabin hint
        self._poly([(390, 252), (430, 252), (430, 300), (400, 300)], fill="#0D2438", outline=WIRE_SOFT, width=1)


        # The harness is derived solely from the live CAN bus state. It
        # deliberately says "SIMULATION CAN" elsewhere when hardware is not
        # connected, rather than implying a physical network is present.
        can_state = snap.get("can", {}).get("bus_state", "IDLE")
        harness = WIRE if can_state == "ACTIVE" else COLORS["offline"]
        harness_width = 2 if can_state == "ACTIVE" else 1
        harness_dash = () if can_state == "ACTIVE" else (4, 3)
        self._line(
            [(267, 328), (328, 328), (350, 347), (500, 347), (620, 347), (690, 390)],
            fill=harness, width=harness_width, dash=harness_dash,
        )
        self._line([(430, 347), (430, 286), (390, 230)], fill=harness, width=1, dash=harness_dash)
        self._line([(575, 347), (575, 285), (560, 175)], fill=harness, width=1, dash=harness_dash)
        if not self._compact:
            hx, hy = self._xy(503, 318)
            self._canvas.create_text(hx, hy, text="CAN", fill=harness, font=("Consolas", 7, "bold"))
        # Vehicle click target (body bounds)
        x1, y1 = self._xy(198, 168)
        x2, y2 = self._xy(778, 410)
        self._hits.append((VEHICLE_ID, x1, y1, x2, y2))

    def _draw_wheel(self, x: float, y: float, r: float, far: bool) -> None:
        rim = WIRE_SOFT if far else WIRE
        self._oval(x, y, r, r * 0.92, fill="#05080C", outline=rim, width=2)
        self._oval(x, y, r * 0.55, r * 0.5, fill="#0C1520", outline=rim, width=1)
        self._oval(x, y, r * 0.18, r * 0.16, fill=WIRE, outline="")

    def _draw_iso_cube(self, x: float, y: float, color: str, selected: bool) -> tuple[int, ...]:
        s = 11 if self._compact else 14
        glow = 22 if selected else 16
        gx, gy = self._xy(x, y)
        g = self._canvas.create_oval(gx - glow, gy - glow, gx + glow, gy + glow, fill="", outline=color, width=1)
        # isometric cube
        dx, dy = 8, 5
        front = self._poly([(x - s, y), (x, y + dy), (x, y + s + dy), (x - s, y + s)], fill=color, outline=COLORS["bg_primary"], width=1)
        side = self._poly([(x, y + dy), (x + dx, y), (x + dx, y + s), (x, y + s + dy)], fill=_hex_lerp(color, "#000000", 0.35), outline=COLORS["bg_primary"], width=1)
        top = self._poly([(x - s, y), (x - s + dx, y - dy), (x + dx, y), (x, y + dy)], fill=_hex_lerp(color, "#FFFFFF", 0.25), outline=COLORS["bg_primary"], width=1)
        return g, front, side, top

    def _draw_nodes(self, snap: dict) -> None:
        canvas = self._canvas
        ecus = snap.get("ecus", {})
        can = snap.get("can", {})
        dim_ok = self._view_mode == "fault"
        for spec in ECU_CATALOG:
            ecu_id = spec["id"]
            ecu = ecus.get(ecu_id)
            if not ecu:
                continue
            layout = NODE_LAYOUT.get(ecu_id)
            if not layout:
                continue
            status = ecu.get("status", "OFFLINE")
            color = status_color(status)
            if dim_ok and status not in {"FAULT", "RECOVERING", "WARNING"}:
                color = COLORS["offline"]
            ax, ay = layout["attach"]
            cx, cy = layout["card"]
            selected = self.selected_id == ecu_id

            px, py = self._xy(ax, ay)
            qx, qy = self._xy(cx, cy)
            link_w = 2 if selected or status in {"FAULT", "RECOVERING"} else 1
            link_kw = {"fill": color, "width": link_w}
            if can.get("bus_state") != "ACTIVE":
                link_kw["dash"] = (4, 3)
            link = canvas.create_line(px, py, qx, qy, **link_kw)
            packet = canvas.create_oval(px - 3, py - 3, px + 3, py + 3, fill=COLORS["accent_glow"], outline="")
            cube = self._draw_iso_cube(ax, ay, color, selected)

            # callout card
            card_w, card_h = (118, 36) if not self._compact else (78, 22)
            if self._compact:
                name = canvas.create_text(qx, qy, text=ecu["name"].replace(" ECU", ""), fill=COLORS["text_primary"], font=("Segoe UI", 7, "bold"))
                st = canvas.create_text(qx, qy + 11, text=status, fill=color, font=("Consolas", 6, "bold"))
                fw = canvas.create_text(qx, qy, text="", fill=COLORS["text_muted"], font=("Consolas", 6), state="hidden")
                rect = canvas.create_rectangle(qx, qy, qx, qy, state="hidden")
                rx1, ry1, rx2, ry2 = qx - 40, qy - 10, qx + 40, qy + 18
            else:
                rx1, ry1 = qx - card_w / 2, qy - card_h / 2
                rx2, ry2 = qx + card_w / 2, qy + card_h / 2
                outline = COLORS["accent"] if selected else color
                rect = canvas.create_rectangle(rx1, ry1, rx2, ry2, fill=COLORS["bg_card"], outline=outline, width=2 if selected else 1)
                name = canvas.create_text((rx1 + rx2) / 2, ry1 + 11, text=ecu["name"].upper(), fill=COLORS["text_primary"], font=("Segoe UI", 8, "bold"))
                st = canvas.create_text(rx1 + 10, ry2 - 12, text=status_mark(status), fill=color, font=("Consolas", 8, "bold"), anchor="w")
                fw = canvas.create_text(rx2 - 8, ry2 - 12, text=ecu.get("firmware", ""), fill=COLORS["text_muted"], font=("Consolas", 7), anchor="e")

            self._hits.append((ecu_id, rx1, ry1, rx2, ry2))
            hx1, hy1 = self._xy(ax - 18, ay - 16)
            hx2, hy2 = self._xy(ax + 18, ay + 22)
            self._hits.append((ecu_id, hx1, hy1, hx2, hy2))

            self._node_items[ecu_id] = {
                "link": link,
                "packet": packet,
                "cube": cube,
                "rect": rect,
                "name": name,
                "status_txt": st,
                "fw": fw,
                "line_pts": (px, py, qx, qy),
                "phase": (hash(ecu_id) % 10) / 10.0,
                "attach": (ax, ay),
            }

        # CAN backbone (visual of DBC catalog — all 6 ECUs share the sim bus)
        if not self._compact:
            self._draw_can_badge(snap)

    def _draw_can_badge(self, snap: dict) -> None:
        can = snap.get("can", {})
        mode = snap.get("mode", "DISCONNECTED")
        state = can.get("bus_state", "IDLE")
        color = COLORS["success"] if state == "ACTIVE" else (COLORS["error"] if state == "ERROR" else COLORS["text_muted"])
        x1, y1 = self._xy(390, 498)
        x2, y2 = self._xy(610, 548)
        rect = self._canvas.create_rectangle(x1, y1, x2, y2, fill=COLORS["bg_card"], outline=color, width=1)
        src = "SIMULATION CAN" if mode != "HARDWARE" else "CAN BUS"
        self._canvas.create_text((x1 + x2) / 2, y1 + 12, text=src, fill=COLORS["text_muted"], font=("Segoe UI", 7, "bold"))
        mark = "● ACTIVE" if state == "ACTIVE" else ("✖ ERROR" if state == "ERROR" else "○ IDLE")
        self._hub_items["can_state"] = self._canvas.create_text((x1 + x2) / 2, y1 + 28, text=f"{mark}   {can.get('messages_per_sec', 0)} msg/s", fill=color, font=("Consolas", 8, "bold"))
        self._hub_items["can_rect"] = rect
        self._hits.append((CAN_ID, x1, y1, x2, y2))

    def _draw_system_view(self, snap: dict, w: int, h: int) -> None:
        canvas = self._canvas
        ox, oy, s = self._xf
        health = snap.get("overall_health", "OFFLINE")
        hc = status_color(health)
        # Vehicle state hub
        vx, vy = self._xy(500, 70)
        canvas.create_rectangle(vx - 90, vy - 22, vx + 90, vy + 22, fill=COLORS["bg_card"], outline=hc, width=2)
        canvas.create_text(vx, vy - 6, text="VEHICLE STATE", fill=COLORS["text_muted"], font=("Segoe UI", 8, "bold"))
        self._hub_items["status"] = canvas.create_text(vx, vy + 8, text=status_mark(health), fill=hc, font=("Consolas", 10, "bold"))
        self._hits.append((VEHICLE_ID, vx - 90, vy - 22, vx + 90, vy + 22))

        ids = [e["id"] for e in ECU_CATALOG if e["id"] in snap.get("ecus", {})]
        n = max(1, len(ids))
        gap = 140
        total = (n - 1) * gap
        start_x = 500 - total / 2
        y = 230
        bus_y = 360
        vcu_y = 470
        for i, ecu_id in enumerate(ids):
            ecu = snap["ecus"][ecu_id]
            color = status_color(ecu["status"])
            x = start_x + i * gap
            px, py = self._xy(x, y)
            canvas.create_line(vx, vy + 22, px, py - 28, fill=color, width=1, dash=(3, 2))
            bx, by = self._xy(x, bus_y)
            canvas.create_line(px, py + 28, bx, by - 10, fill=WIRE_SOFT, width=1)
            selected = self.selected_id == ecu_id
            outline = COLORS["accent"] if selected else color
            rect = canvas.create_rectangle(px - 54, py - 28, px + 54, py + 28, fill=COLORS["bg_card"], outline=outline, width=2 if selected else 1)
            name = canvas.create_text(px, py - 10, text=ecu["name"].upper(), fill=COLORS["text_primary"], font=("Segoe UI", 8, "bold"))
            st = canvas.create_text(px, py + 8, text=status_mark(ecu["status"]), fill=color, font=("Consolas", 8, "bold"))
            self._node_items[ecu_id] = {
                "link": 0, "packet": 0, "cube": (), "rect": rect, "name": name,
                "status_txt": st, "fw": 0, "line_pts": (px, py, bx, by), "phase": i / n,
                "attach": (x, y),
            }
            self._hits.append((ecu_id, px - 54, py - 28, px + 54, py + 28))

        # CAN bus bar
        c1x, c1y = self._xy(start_x - 40, bus_y)
        c2x, c2y = self._xy(start_x + total + 40, bus_y)
        can = snap.get("can", {})
        cc = COLORS["success"] if can.get("bus_state") == "ACTIVE" else COLORS["text_muted"]
        canvas.create_line(c1x, c1y, c2x, c2y, fill=cc, width=3)
        canvas.create_text((c1x + c2x) / 2, c1y - 14, text="CAN BUS", fill=COLORS["text_muted"], font=("Segoe UI", 8, "bold"))
        src = "SIMULATION CAN" if snap.get("mode") != "HARDWARE" else "CAN BUS"
        self._hub_items["can_state"] = canvas.create_text(
            (c1x + c2x) / 2, c1y + 16,
            text=f"{src}  ·  {status_mark(can.get('bus_state', 'IDLE'))}  ·  {can.get('messages_per_sec', 0)} msg/s",
            fill=cc, font=("Consolas", 8, "bold"),
        )
        self._hits.append((CAN_ID, c1x, c1y - 24, c2x, c1y + 28))

        # VCU / STM32 — honest about connection
        stm = bool(snap.get("services", {}).get("stm32"))
        label = "STM32 / VCU  ·  LINK UP" if stm else "STM32 / VCU  ·  SIMULATION GATEWAY"
        color = COLORS["success"] if stm else COLORS["accent"]
        ux, uy = self._xy(500, vcu_y)
        canvas.create_line((c1x + c2x) / 2, c1y, ux, uy - 22, fill=WIRE, width=1)
        canvas.create_rectangle(ux - 160, uy - 22, ux + 160, uy + 22, fill=COLORS["bg_card"], outline=color, width=1)
        canvas.create_text(ux, uy, text=label, fill=color, font=("Consolas", 9, "bold"))

    def _draw_thermal(self, snap: dict) -> None:
        tel = snap.get("telemetry", {})
        engine_t = tel.get("engine_temp")
        cabin_t = tel.get("cabin_temp")
        if isinstance(engine_t, (int, float)):
            col = _heat_color(engine_t, 70, 120)
            self._poly([(218, 300), (318, 292), (322, 358), (220, 364)], fill=col, outline=col, width=1, stipple="gray50")
            x, y = self._xy(268, 270)
            self._canvas.create_text(x, y, text=f"MOTOR  {engine_t:.1f}°C  ·  SIM", fill=col, font=("Consolas", 8, "bold"))
        if isinstance(cabin_t, (int, float)):
            col = _heat_color(cabin_t, 16, 34)
            self._poly([(370, 178), (640, 178), (700, 244), (430, 246)], fill=col, outline=col, width=1, stipple="gray25")
            x, y = self._xy(520, 150)
            self._canvas.create_text(x, y, text=f"CABIN  {cabin_t:.1f}°C  ·  SIM", fill=col, font=("Consolas", 8, "bold"))
        x, y = self._xy(500, 28)
        self._canvas.create_text(
            x, y,
            text="THERMAL DATA  ·  SIMULATION  ·  engine_temp / cabin_temp only  ·  no battery temperature channel",
            fill=COLORS["text_muted"], font=("Segoe UI", 8),
        )

    def _draw_power(self, snap: dict) -> None:
        tel = snap.get("telemetry", {})
        v, i, p = tel.get("battery_voltage"), tel.get("battery_current"), tel.get("battery_power")
        # Battery → motor flow
        self._line([(500, 348), (320, 348), (270, 328)], fill=BATT_GREEN, width=3, arrow="last", arrowshape=(10, 12, 4))
        # Motor → vehicle
        self._line([(250, 340), (250, 400), (278, 400)], fill=MOTOR_ORANGE, width=2, arrow="last", arrowshape=(8, 10, 3))
        self._line([(250, 400), (688, 400)], fill=WIRE, width=1, dash=(4, 3))
        x, y = self._xy(500, 28)
        self._canvas.create_text(
            x, y,
            text=f"POWER FLOW  ·  SIMULATION  ·  {_fmt(v, 'V')}   {_fmt(i, 'A')}   {_fmt(p, 'W')}",
            fill=COLORS["text_primary"], font=("Consolas", 9, "bold"),
        )

    def _draw_fault_banner(self, snap: dict) -> None:
        faults = snap.get("active_faults") or []
        x, y = self._xy(500, 22)
        if not faults:
            self._canvas.create_text(x, y, text="FAULT VIEW  ·  no active faults in Central State", fill=COLORS["success"], font=("Segoe UI", 9, "bold"))
            return
        names = ", ".join(f"{f.get('name', f.get('ecu'))} {f.get('fault_id') or f.get('status')}" for f in faults)
        self._canvas.create_text(x, y, text=f"ACTIVE FAULTS  ·  {names}", fill=COLORS["error"], font=("Segoe UI", 9, "bold"))

    def _draw_hud(self, snap: dict, w: int, h: int) -> None:
        if self._compact:
            fw = snap.get("firmware", "—")
            self._canvas.create_text(8, h - 10, text=f"FW {fw}  ·  live ECU state", anchor="w", fill=COLORS["text_muted"], font=("Segoe UI", 8))
            return
        # corner legend
        self._canvas.create_text(12, 14, text="SDV DIGITAL TWIN", anchor="w", fill=COLORS["accent"], font=("Segoe UI", 9, "bold"))
        self._canvas.create_text(12, 30, text="software state of the vehicle  ·  not a decorative render", anchor="w", fill=COLORS["text_muted"], font=("Segoe UI", 8))

        # right rail
        bx = w - 28
        for i, (label, tag) in enumerate((("+", "zoom_in"), ("−", "zoom_out"), ("↺", "reset"))):
            y = 48 + i * 36
            r = self._canvas.create_rectangle(bx - 16, y - 12, bx + 16, y + 12, fill=COLORS["bg_card"], outline=COLORS["border"], width=1)
            self._canvas.create_text(bx, y, text=label, fill=COLORS["text_primary"], font=("Segoe UI", 11, "bold"))
            self._hits.append((f"__tool_{tag}__", bx - 16, y - 12, bx + 16, y + 12))

    # --------------------------------------------------------- dynamic --

    def _update_dynamic(self, snap: dict) -> None:
        canvas = self._canvas
        recovering = False
        pulse = int(time.time() * 4) % 2
        for ecu_id, items in self._node_items.items():
            ecu = snap.get("ecus", {}).get(ecu_id)
            if not ecu:
                continue
            status = ecu["status"]
            color = status_color(status)
            if status == "RECOVERING":
                recovering = True
                color = COLORS["warning"] if pulse == 0 else COLORS["accent"]
            if self._view_mode == "fault" and status not in {"FAULT", "RECOVERING", "WARNING"}:
                color = COLORS["offline"]
            if items.get("link"):
                canvas.itemconfig(items["link"], fill=color)
            if items.get("status_txt"):
                txt = status_mark(status) if not self._compact else status
                canvas.itemconfig(items["status_txt"], text=txt, fill=color)
            if items.get("fw"):
                canvas.itemconfig(items["fw"], text=ecu.get("firmware", ""))
            if items.get("rect"):
                outline = COLORS["accent"] if self.selected_id == ecu_id else color
                try:
                    canvas.itemconfig(items["rect"], outline=outline)
                except Exception:
                    pass
            cube = items.get("cube") or ()
            if len(cube) >= 4:
                try:
                    canvas.itemconfig(cube[0], outline=color)
                    canvas.itemconfig(cube[1], fill=color)
                    canvas.itemconfig(cube[2], fill=_hex_lerp(color, "#000000", 0.35))
                    canvas.itemconfig(cube[3], fill=_hex_lerp(color, "#FFFFFF", 0.25))
                except Exception:
                    pass
        if self._hub_items.get("status"):
            h = snap.get("overall_health", "—")
            canvas.itemconfig(self._hub_items["status"], text=status_mark(h) if self._view_mode == "system" else h, fill=status_color(h))
        if self._hub_items.get("can_state"):
            can = snap.get("can", {})
            state = can.get("bus_state", "IDLE")
            color = COLORS["success"] if state == "ACTIVE" else (COLORS["error"] if state == "ERROR" else COLORS["text_muted"])
            src = "SIMULATION CAN" if snap.get("mode") != "HARDWARE" else "CAN BUS"
            canvas.itemconfig(
                self._hub_items["can_state"],
                fill=color,
                text=f"{src}  ·  {status_mark(state) if self._view_mode == 'system' else state}  ·  {can.get('messages_per_sec', 0)} msg/s"
                if self._view_mode == "system"
                else f"{'● ACTIVE' if state == 'ACTIVE' else ('✖ ERROR' if state == 'ERROR' else '○ IDLE')}   {can.get('messages_per_sec', 0)} msg/s",
            )

    # ---------------------------------------------------------- events --

    def _hit(self, x: float, y: float) -> str | None:
        # last-drawn is on top — search reverse, skip vehicle body if a node also hits
        found_vehicle = None
        for ecu_id, x1, y1, x2, y2 in reversed(self._hits):
            if x1 <= x <= x2 and y1 <= y <= y2:
                if ecu_id == VEHICLE_ID:
                    found_vehicle = ecu_id
                    continue
                return ecu_id
        return found_vehicle

    def _on_click(self, event) -> None:
        target = self._hit(event.x, event.y)
        if target == "__tool_zoom_in__":
            self.set_zoom(0.08)
            return
        if target == "__tool_zoom_out__":
            self.set_zoom(-0.08)
            return
        if target == "__tool_reset__":
            self.reset_view()
            return
        self.selected_id = target
        self._stamp = None
        if self._on_select:
            self._on_select(target)
        self.refresh()

    def _on_motion(self, event) -> None:
        target = self._hit(event.x, event.y)
        self._canvas.configure(cursor="hand2" if target else "arrow")
        if not target or target.startswith("__tool_"):
            self._hide_tip()
            return
        snap = self._last_snap
        if target == CAN_ID:
            can = snap.get("can", {})
            text = f"CAN  {can.get('bus_state', '—')}  ·  {can.get('messages_per_sec', 0)} msg/s"
        elif target == VEHICLE_ID:
            text = f"VEHICLE  {snap.get('overall_health', '—')}  ·  FW {snap.get('firmware', '—')}"
        else:
            ecu = snap.get("ecus", {}).get(target, {})
            text = f"{ecu.get('name', target)}  {status_mark(ecu.get('status', '—'))}  ·  {ecu.get('health', 0)}%"
        self._show_tip(event.x, event.y, text)

    def _show_tip(self, x: int, y: int, text: str) -> None:
        if not self._tip_txt:
            return
        canvas = self._canvas
        canvas.itemconfig(self._tip_txt, text=text, state="normal")
        canvas.coords(self._tip_txt, x + 14, y + 12)
        bbox = canvas.bbox(self._tip_txt)
        if bbox and self._tip_bg:
            canvas.coords(self._tip_bg, bbox[0] - 6, bbox[1] - 4, bbox[2] + 6, bbox[3] + 4)
            canvas.itemconfig(self._tip_bg, state="normal")
            canvas.tag_raise(self._tip_bg)
            canvas.tag_raise(self._tip_txt)

    def _hide_tip(self) -> None:
        if self._tip_txt:
            self._canvas.itemconfig(self._tip_txt, state="hidden")
        if self._tip_bg:
            self._canvas.itemconfig(self._tip_bg, state="hidden")

    def _arm_anim(self) -> None:
        self._anim_job = self.after(80, self._anim_packets)

    def _anim_packets(self) -> None:
        if not self.winfo_exists():
            return
        if self._view_mode in {"engineering", "power", "fault"} and not self._compact:
            self._packet_t = (self._packet_t + 0.045) % 1.0
            snap = self._last_snap
            can_active = snap.get("can", {}).get("bus_state") == "ACTIVE"
            for ecu_id, items in self._node_items.items():
                pkt = items.get("packet")
                pts = items.get("line_pts")
                if not pkt or not pts:
                    continue
                ecu = snap.get("ecus", {}).get(ecu_id, {})
                status = ecu.get("status")
                if not can_active or status in {"OFFLINE", "FAULT"}:
                    self._canvas.itemconfig(pkt, state="hidden")
                    continue
                self._canvas.itemconfig(pkt, state="normal")
                t = (self._packet_t + items.get("phase", 0)) % 1.0
                x1, y1, x2, y2 = pts
                x = x1 + (x2 - x1) * t
                y = y1 + (y2 - y1) * t
                self._canvas.coords(pkt, x - 3, y - 3, x + 3, y + 3)
        self._anim_job = self.after(80, self._anim_packets)

    def _on_destroy(self, event) -> None:
        if event.widget is not self:
            return
        if self._anim_job:
            try:
                self.after_cancel(self._anim_job)
            except Exception:
                pass
            self._anim_job = None
