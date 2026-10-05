"""OTA Manager view with version history, metadata summary, rollback, and
security status. The UI keeps the same dashboard shape but displays the fields
required for engineering-grade OTA visibility.
"""

from __future__ import annotations

from tkinter import messagebox

import customtkinter as ctk

from sdv_console.components.widgets import caption, section_title
from sdv_console.config import COLORS, ECU_CATALOG


class OTAManagerView(ctk.CTkScrollableFrame):
    def __init__(self, master, platform, **kwargs) -> None:
        super().__init__(master, fg_color=COLORS["bg_primary"], corner_radius=0, **kwargs)
        self.platform = platform
        self._ecu = ctk.StringVar(value="Battery ECU")
        self._ver = ctk.StringVar(value="v1.2.0")
        self._stamp = None
        self._banner_visible = False
        self._hist_status = None
        self._build()

    def _build(self) -> None:
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=24, pady=16)
        section_title(head, "OTA Manager").pack(anchor="w")
        caption(head, "Dashboard → Validate → Package → ESP32 Gateway → STM32 → Firmware Update → Version Changed. Security, metadata, rollback, and history remain visible to the engineer at all times.").pack(anchor="w")

        controls = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=10)
        controls.pack(fill="x", padx=24, pady=8)
        ctk.CTkLabel(controls, text="Target ECU", text_color=COLORS["text_muted"]).grid(row=0, column=0, padx=12, pady=12, sticky="w")
        ctk.CTkOptionMenu(controls, variable=self._ecu, values=[e["name"] for e in ECU_CATALOG], width=180).grid(row=0, column=1, padx=8)
        ctk.CTkLabel(controls, text="Target firmware", text_color=COLORS["text_muted"]).grid(row=0, column=2, padx=12, sticky="w")
        ctk.CTkOptionMenu(controls, variable=self._ver, values=["v1.1.0", "v1.2.0", "v2.0.0"], width=110).grid(row=0, column=3, padx=8)
        ctk.CTkButton(controls, text="Start OTA deployment", command=self._start).grid(row=0, column=4, padx=12)
        ctk.CTkButton(controls, text="Rollback", command=self._rollback, fg_color=COLORS["warning"], hover_color="#C78900").grid(row=0, column=5, padx=12)

        self._hero = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=12)
        self._hero.pack(fill="x", padx=24, pady=12)

        self._banner = ctk.CTkFrame(self._hero, fg_color=COLORS["success"], corner_radius=10)
        self._banner_label = ctk.CTkLabel(self._banner, text="", font=ctk.CTkFont(size=15, weight="bold"), text_color="#052E16")
        self._banner_label.pack(padx=16, pady=10, anchor="w")

        self._title = ctk.CTkLabel(self._hero, text="OTA DEPLOYMENT", font=ctk.CTkFont(size=18, weight="bold"), text_color=COLORS["text_primary"])
        self._title.pack(anchor="w", padx=20, pady=(16, 4))
        self._versions = ctk.CTkLabel(self._hero, text="", font=ctk.CTkFont(size=14), text_color=COLORS["text_secondary"])
        self._versions.pack(anchor="w", padx=20)
        self._details = ctk.CTkLabel(self._hero, text="", justify="left", font=ctk.CTkFont(size=13), text_color=COLORS["text_primary"])
        self._details.pack(anchor="w", padx=20, pady=(8, 0))
        self._checks = ctk.CTkFrame(self._hero, fg_color="transparent")
        self._checks.pack(fill="x", padx=20, pady=8)
        self._bar = ctk.CTkProgressBar(self._hero, height=18)
        self._bar.pack(fill="x", padx=20, pady=8)
        self._bar.set(0)
        self._pct = ctk.CTkLabel(self._hero, text="0%", font=ctk.CTkFont(size=13, weight="bold"))
        self._pct.pack(anchor="e", padx=20)
        self._status = ctk.CTkLabel(self._hero, text="IDLE", font=ctk.CTkFont(size=16, weight="bold"), text_color=COLORS["text_muted"])
        self._status.pack(anchor="w", padx=20, pady=(4, 8))

        section_title(self, "Key Features & OTA History").pack(anchor="w", padx=24, pady=(8, 4))
        self._features = ctk.CTkTextbox(self, height=110, fg_color=COLORS["bg_card"], font=ctk.CTkFont(family="Consolas", size=12))
        self._features.pack(fill="x", padx=24, pady=(0, 12))
        self._hist = ctk.CTkTextbox(self, height=130, fg_color=COLORS["bg_card"], font=ctk.CTkFont(family="Consolas", size=12))
        self._hist.pack(fill="x", padx=24, pady=(0, 20))

    def _prompt_pin(self, title: str, prompt: str) -> str | None:
        dialog = ctk.CTkInputDialog(title=title, text=prompt)
        value = dialog.get_input()
        if value is None:
            return None
        pin = str(value).strip()
        if not pin:
            self._status.configure(text="AUTHENTICATION: REQUIRED", text_color=COLORS["warning"])
            return None
        return pin

    def _start(self) -> None:
        pin = self._prompt_pin("OTA Security Verification", "Enter the engineering PIN to continue with firmware deployment.")
        if pin is None:
            self._status.configure(text="AUTHENTICATION: NOT VERIFIED", text_color=COLORS["warning"])
            return
        res = self.platform.start_ota(self._ecu.get(), self._ver.get(), requested_by="eng-user", role="engineering", pin=pin)
        if not res.get("ok"):
            self._status.configure(text=f"ERROR: {res.get('error')}", text_color=COLORS["error"])
            return
        self._status.configure(text="AUTHENTICATION: VERIFIED", text_color=COLORS["success"])

    def _rollback(self) -> None:
        if not messagebox.askyesno("Rollback firmware", "Rollback to the last known-good firmware version? This changes the active ECU firmware state."):
            self._status.configure(text="ROLLBACK: CANCELLED", text_color=COLORS["warning"])
            return
        pin = self._prompt_pin("Rollback Authorization", "Enter the engineering PIN to authorize firmware rollback.")
        if pin is None:
            self._status.configure(text="ROLLBACK AUTH: NOT VERIFIED", text_color=COLORS["warning"])
            return
        res = self.platform.ota_service.rollback(requested_by="eng-user", role="engineering", pin=pin)
        if not res.get("ok"):
            self._status.configure(text=f"ROLLBACK ERROR: {res.get('error')}", text_color=COLORS["error"])
            return
        self._status.configure(text="ROLLBACK AUTH: VERIFIED", text_color=COLORS["success"])

    def refresh(self) -> None:
        ota = self.platform.snapshot()["ota"]
        stamp = (ota.get("status"), ota.get("progress"), tuple(sorted((ota.get("checks") or {}).items())), tuple((ota.get("feature_changes") or [])))
        if stamp == self._stamp:
            return
        self._stamp = stamp

        current = ota.get("current_version") or "v1.0.0"
        target = ota.get("target_version") or current
        ecu = ota.get("target_ecu") or "Battery ECU"
        update_type = ota.get("update_type") or "FULL OTA"
        package_type = ota.get("package_type") or "full"
        features = ota.get("feature_changes") or []
        self._versions.configure(text=f"Current {current}     Target {target}     ECU {ecu}")
        auth_state = ota.get("authentication_status") or "REQUIRED"
        self._details.configure(
            text=(
                f"Update Type: {update_type}\n"
                f"Package: {package_type.upper()}\n"
                f"Integrity: {'VERIFIED' if ota.get('integrity_verified') else 'PENDING'}\n"
                f"Authentication: {auth_state}\n"
                f"Rollback: {'AVAILABLE' if ota.get('rollback_available') else 'NOT AVAILABLE'}\n"
                f"Last Known Good: {ota.get('last_known_good_version') or current}"
            )
        )

        for c in self._checks.winfo_children():
            c.destroy()
        for name, key in [
            ("Firmware Validation", "firmware_validation"),
            ("Integrity Check", "integrity_check"),
            ("Compatibility Check", "compatibility_check"),
            ("Authentication", "authenticity_check"),
        ]:
            ok = (ota.get("checks") or {}).get(key)
            mark, color = ("✓", COLORS["success"]) if ok else ("○", COLORS["text_muted"])
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
            self._banner_label.configure(text=f"✓ SIMULATION OTA DEPLOYMENT COMPLETE — {ecu} is now running {target} (was {ota.get('from_version', '?')})")
        elif self._banner_visible:
            self._banner.pack_forget()
            self._banner_visible = False

        self._features.delete("1.0", "end")
        if features:
            for feature in features:
                self._features.insert("end", f"• {feature}\n")
        else:
            self._features.insert("end", "Feature change information unavailable.\n")

        if status != self._hist_status:
            self._hist_status = status
            self._hist.delete("1.0", "end")
            rows = self.platform.history.query_ota()
            if not rows:
                self._hist.insert("end", "No completed deployments yet.\n")
                return
            for row in rows:
                details = row.get("details") or {}
                result = row.get("result") or "UNKNOWN"
                package = row.get("package_type") or details.get("package_type") or "full"
                update = row.get("update_type") or details.get("update_type") or "FULL OTA"
                self._hist.insert("end", f"{row['timestamp'][11:19]}   {row['target_ecu']:<16}  {row['from_version']} → {row['to_version']}   {result}   {package.upper()}   {update}\n")
