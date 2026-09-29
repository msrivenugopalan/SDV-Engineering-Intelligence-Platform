"""Digital Twin page — visualization modes + inspector over Central State."""

from __future__ import annotations

import customtkinter as ctk

from sdv_console.components.digital_twin import CAN_ID, ECU_TELEMETRY, VEHICLE_ID, DigitalTwin
from sdv_console.components.widgets import caption, section_title, status_color, status_mark
from sdv_console.config import COLORS

MODE_VALUES = [
    "3D / Engineering",
    "System View",
    "Thermal View",
    "Power Flow",
    "Fault View",
]
MODE_MAP = {
    "3D / Engineering": "engineering",
    "System View": "system",
    "Thermal View": "thermal",
    "Power Flow": "power",
    "Fault View": "fault",
}


class DigitalTwinView(ctk.CTkFrame):
    def __init__(self, master, platform, **kwargs) -> None:
        super().__init__(master, fg_color=COLORS["bg_primary"], corner_radius=0, **kwargs)
        self.platform = platform
        self._fields: dict[str, ctk.CTkLabel] = {}
        self._build()

    def _build(self) -> None:
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=18, pady=(12, 4))
        left = ctk.CTkFrame(head, fg_color="transparent")
        left.pack(side="left", fill="x", expand=True)
        section_title(left, "Digital Twin").pack(anchor="w")
        caption(
            left,
            "Interactive SDV engineering workspace. State is Central State — faults, recovery, OTA, CAN, and telemetry "
            "update this view; the twin never invents a second vehicle model.",
        ).pack(anchor="w")

        badges = ctk.CTkFrame(head, fg_color="transparent")
        badges.pack(side="right", padx=(12, 0))
        self._mode_badge = self._badge(badges, "SIMULATION MODE", COLORS["accent"])
        self._health_badge = self._badge(badges, "● HEALTHY", COLORS["success"])
        self._fw_badge = self._badge(badges, "FW —", COLORS["text_secondary"])
        self._ota_badge = self._badge(badges, "OTA IDLE", COLORS["text_muted"])

        modes = ctk.CTkFrame(self, fg_color="transparent")
        modes.pack(fill="x", padx=18, pady=(4, 6))
        self._mode_bar = ctk.CTkSegmentedButton(
            modes,
            values=MODE_VALUES,
            command=self._on_mode,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color=COLORS["bg_card"],
            selected_color=COLORS["accent"],
            selected_hover_color=COLORS["accent_glow"],
            unselected_color=COLORS["bg_card_alt"],
            unselected_hover_color=COLORS["border"],
            text_color=COLORS["text_primary"],
        )
        self._mode_bar.set("3D / Engineering")
        self._mode_bar.pack(side="left")

        body = ctk.CTkFrame(self, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=12, pady=(0, 12))
        body.grid_columnconfigure(0, weight=5)
        body.grid_columnconfigure(1, weight=2)
        body.grid_rowconfigure(0, weight=1)

        stage = ctk.CTkFrame(body, fg_color=COLORS["bg_card"], corner_radius=12, border_width=1, border_color=COLORS["border"])
        stage.grid(row=0, column=0, sticky="nsew", padx=(0, 8))
        self._twin = DigitalTwin(stage, self.platform.snapshot, compact=False, on_select=self._on_select)
        self._twin.pack(fill="both", expand=True, padx=4, pady=4)

        inspect = ctk.CTkFrame(body, fg_color=COLORS["bg_card"], corner_radius=12, border_width=1, border_color=COLORS["border"], width=320)
        inspect.grid(row=0, column=1, sticky="nsew")
        inspect.grid_propagate(False)
        self._build_inspector(inspect)

    def _badge(self, parent, text: str, color: str) -> ctk.CTkLabel:
        wrap = ctk.CTkFrame(parent, fg_color=COLORS["bg_card"], corner_radius=8, border_width=1, border_color=COLORS["border"])
        wrap.pack(side="left", padx=4)
        lab = ctk.CTkLabel(wrap, text=text, font=ctk.CTkFont(family="Consolas", size=11, weight="bold"), text_color=color)
        lab.pack(padx=10, pady=6)
        return lab

    def _build_inspector(self, parent) -> None:
        pad = ctk.CTkFrame(parent, fg_color="transparent")
        pad.pack(fill="both", expand=True, padx=14, pady=12)
        ctk.CTkLabel(pad, text="INSPECTOR", font=ctk.CTkFont(size=11, weight="bold"), text_color=COLORS["accent"]).pack(anchor="w")
        self._insp_title = ctk.CTkLabel(pad, text="VEHICLE", font=ctk.CTkFont(size=16, weight="bold"), text_color=COLORS["text_primary"], anchor="w")
        self._insp_title.pack(anchor="w", pady=(4, 0))
        self._insp_status = ctk.CTkLabel(pad, text="—", font=ctk.CTkFont(family="Consolas", size=13, weight="bold"), anchor="w")
        self._insp_status.pack(anchor="w", pady=(0, 8))

        self._insp_body = ctk.CTkFrame(pad, fg_color="transparent")
        self._insp_body.pack(fill="both", expand=True)
        keys = [
            ("task", "TASK"),
            ("task_state", "TASK STATE"),
            ("firmware", "FIRMWARE"),
            ("health", "HEALTH"),
            ("fault", "FAULT"),
            ("recovery", "RECOVERY"),
            ("last_event", "LAST EVENT"),
            ("updated", "LAST UPDATE"),
            ("comm", "COMMUNICATION"),
            ("t1", "TELEMETRY"),
            ("t2", ""),
            ("t3", ""),
            ("t4", ""),
            ("t5", ""),
            ("domain", "DOMAIN"),
        ]
        for key, label in keys:
            row = ctk.CTkFrame(self._insp_body, fg_color="transparent")
            row.pack(fill="x", pady=2)
            lab = ctk.CTkLabel(row, text=label, font=ctk.CTkFont(size=9), text_color=COLORS["text_muted"], width=110, anchor="w")
            lab.pack(side="left")
            val = ctk.CTkLabel(row, text="—", font=ctk.CTkFont(family="Consolas", size=11), text_color=COLORS["text_primary"], anchor="w", wraplength=180, justify="left")
            val.pack(side="left", fill="x", expand=True)
            self._fields[key] = val
            self._fields[f"{key}_lab"] = lab

        hint = ctk.CTkLabel(
            pad,
            text="Click an ECU, the vehicle, or CAN. Hover for a tooltip. Modes are layers on the same snapshot.",
            font=ctk.CTkFont(size=10),
            text_color=COLORS["text_muted"],
            wraplength=280,
            justify="left",
            anchor="w",
        )
        hint.pack(anchor="w", pady=(10, 0))

    def _on_mode(self, value: str) -> None:
        self._twin.set_view_mode(MODE_MAP.get(value, "engineering"))

    def _on_select(self, _target: str | None) -> None:
        self._fill_inspector(self.platform.snapshot())

    def refresh(self) -> None:
        snap = self.platform.snapshot()
        self._twin.refresh()
        self._refresh_badges(snap)
        self._fill_inspector(snap)

    def _refresh_badges(self, snap: dict) -> None:
        mode = snap.get("mode", "DISCONNECTED")
        if mode == "SIMULATION":
            self._mode_badge.configure(text="SIMULATION MODE", text_color=COLORS["accent"])
        elif mode == "HARDWARE":
            stm = snap.get("services", {}).get("stm32")
            esp = snap.get("services", {}).get("esp32")
            extra = ""
            if stm:
                extra = " · STM32"
            if esp:
                extra += " · ESP32"
            self._mode_badge.configure(text=f"HARDWARE MODE{extra}", text_color=COLORS["success"])
        else:
            self._mode_badge.configure(text="DISCONNECTED", text_color=COLORS["text_muted"])

        health = snap.get("overall_health", "OFFLINE")
        self._health_badge.configure(text=status_mark(health), text_color=status_color(health))
        self._fw_badge.configure(text=f"FW {snap.get('firmware', '—')}", text_color=COLORS["accent"])

        ota = snap.get("ota", {})
        st = ota.get("status", "IDLE")
        if st in {"VALIDATING", "DOWNLOADING", "INSTALLING"}:
            self._ota_badge.configure(text=f"OTA UPDATING {ota.get('progress', 0)}%", text_color=COLORS["warning"])
        elif st == "COMPLETED":
            self._ota_badge.configure(text="OTA UPDATED", text_color=COLORS["success"])
        elif st == "FAILED":
            self._ota_badge.configure(text="OTA FAILED", text_color=COLORS["error"])
        else:
            self._ota_badge.configure(text="OTA IDLE", text_color=COLORS["text_muted"])

    def _fill_inspector(self, snap: dict) -> None:
        target = self._twin.selected_id
        if target == CAN_ID:
            self._fill_can(snap)
            return
        if target and target in snap.get("ecus", {}):
            self._fill_ecu(snap, target)
            return
        self._fill_vehicle(snap)

    def _set(self, key: str, value: str, label: str | None = None, color: str | None = None) -> None:
        if label is not None and f"{key}_lab" in self._fields:
            self._fields[f"{key}_lab"].configure(text=label)
        self._fields[key].configure(text=value, text_color=color or COLORS["text_primary"])

    def _fill_vehicle(self, snap: dict) -> None:
        health = snap.get("overall_health", "OFFLINE")
        self._insp_title.configure(text="VEHICLE")
        self._insp_status.configure(text=status_mark(health), text_color=status_color(health))
        tel = snap.get("telemetry", {})
        rec = snap.get("recovery", {})
        ota = snap.get("ota", {})
        faults = snap.get("active_faults") or []
        self._set("task", "VehicleState + EventBus")
        self._set("task_state", tel.get("vehicle_state", "—"), "OPERATING")
        self._set("firmware", snap.get("firmware", "—"))
        self._set("health", health, color=status_color(health))
        self._set("fault", ", ".join(f.get("fault_id") or f.get("ecu", "") for f in faults) or "none")
        self._set("recovery", rec.get("status", "IDLE") + (f" · {rec.get('ecu')}" if rec.get("ecu") else ""))
        self._set("last_event", (snap.get("recent_events") or [{}])[0].get("event_type", "—") if snap.get("recent_events") else "—")
        self._set("updated", (snap.get("uptime_started") or "")[11:19] or "—", "UPTIME FROM")
        can = snap.get("can", {})
        src = "SIMULATION CAN" if snap.get("mode") != "HARDWARE" else "CAN"
        self._set("comm", f"{src} · {can.get('bus_state', '—')} · {can.get('messages_per_sec', 0)} msg/s")
        self._set("t1", _kv("Speed", tel.get("vehicle_speed"), "km/h"), "TELEMETRY")
        self._set("t2", _kv("SoC", tel.get("battery_soc"), "%"))
        self._set("t3", _kv("Voltage", tel.get("battery_voltage"), "V"))
        self._set("t4", _kv("Power", tel.get("battery_power"), "W"))
        self._set("t5", f"OTA {ota.get('status', 'IDLE')}  {snap.get('firmware', '')}")
        self._set("domain", "software-defined vehicle  ·  virtual ECU network")

    def _fill_ecu(self, snap: dict, ecu_id: str) -> None:
        ecu = snap["ecus"][ecu_id]
        tel = snap.get("telemetry", {})
        rec = snap.get("recovery", {})
        can = snap.get("can", {})
        status = ecu.get("status", "OFFLINE")
        self._insp_title.configure(text=ecu.get("name", ecu_id).upper())
        self._insp_status.configure(text=status_mark(status), text_color=status_color(status))
        task_state = "RUNNING" if status not in {"OFFLINE"} else "SUSPENDED"
        if status == "FAULT":
            task_state = "FAULTED"
        elif status == "RECOVERING":
            task_state = "RECOVERING"
        self._set("task", ecu.get("task", "—"))
        self._set("task_state", task_state, "TASK STATE")
        self._set("firmware", ecu.get("firmware", snap.get("firmware", "—")))
        self._set("health", f"{ecu.get('health', 0)}%")
        self._set("fault", ecu.get("fault_id") or "none")
        rec_txt = ecu.get("recovery_state", "IDLE")
        if rec.get("ecu") == ecu_id:
            rec_txt = f"{rec.get('status', rec_txt)}"
        self._set("recovery", rec_txt)
        self._set("last_event", ecu.get("last_event", "—"))
        ts = (ecu.get("last_update") or "")[11:19]
        self._set("updated", ts or "—", "LAST UPDATE")
        src = "SIMULATION CAN" if snap.get("mode") != "HARDWARE" else "CAN"
        self._set("comm", f"{src} · {can.get('bus_state', '—')}")
        rows = ECU_TELEMETRY.get(ecu_id, [])
        keys = ["t1", "t2", "t3", "t4", "t5"]
        if rows:
            self._set("t1", _kv(rows[0][1], tel.get(rows[0][0]), rows[0][2]), "TELEMETRY")
        else:
            self._set("t1", "no dedicated channel", "TELEMETRY")
        for i, key in enumerate(keys[1:], start=1):
            if i < len(rows):
                spec = rows[i]
                self._set(key, _kv(spec[1], tel.get(spec[0]), spec[2]))
            else:
                self._set(key, "")
        domain = {
            "engine": "POWERTRAIN domain (Motor ECU / EngineTask)",
            "battery": "ENERGY domain (Battery ECU — not a separate BMS ECU)",
            "brake": "CHASSIS domain",
            "steering": "CHASSIS domain",
            "climate": "CABIN domain",
            "adas": "ADAS domain",
        }.get(ecu_id, "virtual ECU")
        self._set("domain", domain)

    def _fill_can(self, snap: dict) -> None:
        can = snap.get("can", {})
        state = can.get("bus_state", "IDLE")
        self._insp_title.configure(text="CAN BUS")
        self._insp_status.configure(text=status_mark(state if state != "ACTIVE" else "HEALTHY") if state != "ACTIVE" else "● ACTIVE", text_color=status_color("HEALTHY" if state == "ACTIVE" else ("FAULT" if state == "ERROR" else "OFFLINE")))
        mode = snap.get("mode", "DISCONNECTED")
        self._set("task", "shared virtual CAN (DBC catalog)")
        self._set("task_state", "SIMULATION" if mode != "HARDWARE" else "HARDWARE", "SOURCE")
        self._set("firmware", snap.get("firmware", "—"), "VEHICLE FW")
        self._set("health", state, color=status_color("HEALTHY" if state == "ACTIVE" else ("FAULT" if state == "ERROR" else "OFFLINE")))
        self._set("fault", f"{can.get('error_count', 0)} error frames")
        self._set("recovery", "—")
        self._set("last_event", f"{can.get('message_count', 0)} frames total")
        self._set("updated", f"{can.get('messages_per_sec', 0)} msg/s", "RATE")
        self._set("comm", "Motor / Battery / Brake / Steering / Climate / ADAS on one bus")
        self._set("t1", "0x101 MotorStatus → ADAS ECU", "DBC")
        self._set("t2", "0x102 BatteryStatus → Motor ECU")
        self._set("t3", "0x103 BrakeStatus → ADAS ECU")
        self._set("t4", "0x104 SteeringStatus → ADAS ECU")
        self._set("t5", "0x105 / 0x106 Climate / ADAS")
        self._set("domain", "do not treat this as a physical CAN analyzer unless HARDWARE MODE is shown")


def _kv(label: str, value, unit: str = "") -> str:
    if value is None or value == "":
        return f"{label}  —"
    if isinstance(value, float):
        text = f"{value:.1f}" if abs(value) >= 10 else f"{value:.2f}"
    else:
        text = str(value)
    return f"{label}  {text} {unit}".strip()
