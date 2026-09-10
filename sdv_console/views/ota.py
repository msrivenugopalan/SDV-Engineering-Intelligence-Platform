"""OTA Manager (architecture doc §13). VALIDATING -> DOWNLOADING ->
INSTALLING -> COMPLETED, with a hard-to-miss banner on success — the moment
your guide asks "what changes visually", this is the answer.
"""

from __future__ import annotations

import customtkinter as ctk

from sdv_console.components.widgets import caption, section_title
from sdv_console.config import COLORS, ECU_CATALOG


class OTAManagerView(ctk.CTkScrollableFrame):
    def __init__(self, master, platform, **kwargs) -> None:
        super().__init__(master, fg_color=COLORS["bg_primary"], corner_radius=0, **kwargs)
        self.platform = platform
        self._ecu = ctk.StringVar(value="Battery ECU")
        self._ver = ctk.StringVar(value="v2.0.0")
        self._stamp = None
        self._banner_visible = False
        self._hist_status = None
        self._build()

    def _build(self) -> None:
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=24, pady=16)
        section_title(head, "OTA Manager").pack(anchor="w")
        caption(head, "Dashboard \u2192 Validate \u2192 Package \u2192 ESP32 Gateway \u2192 STM32 \u2192 Firmware Update \u2192 Version Changed. "
                       "After success, the version state updates everywhere it's shown: header, this page, ECU cards, logs, history.").pack(anchor="w")

        controls = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=10)
        controls.pack(fill="x", padx=24, pady=8)
        ctk.CTkLabel(controls, text="Target ECU", text_color=COLORS["text_muted"]).grid(row=0, column=0, padx=12, pady=12, sticky="w")
        ctk.CTkOptionMenu(controls, variable=self._ecu, values=[e["name"] for e in ECU_CATALOG], width=180).grid(row=0, column=1, padx=8)
        ctk.CTkLabel(controls, text="Target firmware", text_color=COLORS["text_muted"]).grid(row=0, column=2, padx=12, sticky="w")
        ctk.CTkOptionMenu(controls, variable=self._ver, values=["v1.1.0", "v2.0.0"], width=100).grid(row=0, column=3, padx=8)
        ctk.CTkButton(controls, text="Start OTA deployment", command=self._start).grid(row=0, column=4, padx=16)

        self._hero = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=12)
        self._hero.pack(fill="x", padx=24, pady=12)

        self._banner = ctk.CTkFrame(self._hero, fg_color=COLORS["success"], corner_radius=10)
        self._banner_label = ctk.CTkLabel(self._banner, text="", font=ctk.CTkFont(size=15, weight="bold"), text_color="#052E16")
        self._banner_label.pack(padx=16, pady=10, anchor="w")

        self._title = ctk.CTkLabel(self._hero, text="OTA DEPLOYMENT", font=ctk.CTkFont(size=18, weight="bold"), text_color=COLORS["text_primary"])
        self._title.pack(anchor="w", padx=20, pady=(16, 4))
        self._versions = ctk.CTkLabel(self._hero, text="", font=ctk.CTkFont(size=14), text_color=COLORS["text_secondary"])
        self._versions.pack(anchor="w", padx=20)
        self._checks = ctk.CTkFrame(self._hero, fg_color="transparent")
        self._checks.pack(fill="x", padx=20, pady=8)
        self._bar = ctk.CTkProgressBar(self._hero, height=18)
        self._bar.pack(fill="x", padx=20, pady=8)
        self._bar.set(0)
        self._pct = ctk.CTkLabel(self._hero, text="0%", font=ctk.CTkFont(size=13, weight="bold"))
        self._pct.pack(anchor="e", padx=20)
        self._status = ctk.CTkLabel(self._hero, text="IDLE", font=ctk.CTkFont(size=16, weight="bold"), text_color=COLORS["text_muted"])
        self._status.pack(anchor="w", padx=20, pady=(4, 16))

        section_title(self, "OTA History").pack(anchor="w", padx=24, pady=(8, 4))
        self._hist = ctk.CTkTextbox(self, height=140, fg_color=COLORS["bg_card"], font=ctk.CTkFont(family="Consolas", size=12))
        self._hist.pack(fill="x", padx=24, pady=(0, 20))

    def _start(self) -> None:
        res = self.platform.start_ota(self._ecu.get(), self._ver.get())
        if not res.get("ok"):
            self._status.configure(text=f"ERROR: {res.get('error')}", text_color=COLORS["error"])

    def refresh(self) -> None:
        ota = self.platform.snapshot()["ota"]
        stamp = (ota.get("status"), ota.get("progress"), tuple(sorted((ota.get("checks") or {}).items())))
        if stamp == self._stamp:
            return
        self._stamp = stamp

        self._versions.configure(text=f"Current {ota.get('current_version')}     Target {ota.get('target_version')}     ECU {ota.get('target_ecu')}")
        for c in self._checks.winfo_children():
            c.destroy()
        for name, key in [("Firmware Validation", "firmware_validation"), ("Integrity Check", "integrity_check"), ("Compatibility Check", "compatibility_check")]:
            ok = (ota.get("checks") or {}).get(key)
            mark, color = ("\u2713", COLORS["success"]) if ok else ("\u25CB", COLORS["text_muted"])
            ctk.CTkLabel(self._checks, text=f"{name} {mark}", text_color=color, font=ctk.CTkFont(size=13, weight="bold")).pack(side="left", padx=(0, 18))

        self._bar.set((ota.get("progress") or 0) / 100)
        self._pct.configure(text=f"{ota.get('progress') or 0}%")

        status = ota.get("status") or "IDLE"
        color = COLORS["success"] if status == "COMPLETED" else COLORS["warning"] if status != "IDLE" else COLORS["text_muted"]
        self._status.configure(text=f"STATUS: {status}", text_color=color)

        if status == "COMPLETED":
            if not self._banner_visible:
                self._banner.pack(fill="x", padx=20, pady=(0, 12), before=self._title)
                self._banner_visible = True
            self._banner_label.configure(text=f"\u2713  DEPLOYMENT COMPLETE — {ota.get('target_ecu', 'ECU')} is now running {ota.get('target_version')} (was {ota.get('from_version', '?')})")
        elif self._banner_visible:
            self._banner.pack_forget()
            self._banner_visible = False

        if status != self._hist_status:
            self._hist_status = status
            self._hist.delete("1.0", "end")
            rows = self.platform.history.query_ota()
            if not rows:
                self._hist.insert("end", "No completed deployments yet.\n")
                return
            for row in rows:
                self._hist.insert("end", f"{row['timestamp'][11:19]}   {row['target_ecu']:<16}  {row['from_version']} \u2192 {row['to_version']}   {row['result']}\n")
