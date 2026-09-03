"""OTA workflow visualization — engineering demo, not a secure bootloader."""

import customtkinter as ctk

from sdv_console.components.widgets import caption, section_title
from sdv_console.config import COLORS, ECU_CATALOG
from sdv_console.platform import EngineeringPlatform


class OTAManagerView(ctk.CTkScrollableFrame):
    def __init__(self, master, platform: EngineeringPlatform, **kwargs) -> None:
        super().__init__(master, fg_color=COLORS["bg_primary"], corner_radius=0, **kwargs)
        self.platform = platform
        self._ecu = ctk.StringVar(value="Battery ECU")
        self._ver = ctk.StringVar(value="v1.1")
        self._build()

    def _build(self) -> None:
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=24, pady=16)
        section_title(head, "OTA Manager").pack(anchor="w")
        caption(
            head,
            "This panel demonstrates an OTA workflow (validate → transfer via ESP32 → STM32 ECU update → verify). "
            "It is not a production-grade secure automotive bootloader.",
        ).pack(anchor="w")

        controls = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=10)
        controls.pack(fill="x", padx=24, pady=8)
        ctk.CTkLabel(controls, text="Target ECU", text_color=COLORS["text_muted"]).grid(row=0, column=0, padx=12, pady=12, sticky="w")
        ctk.CTkOptionMenu(controls, variable=self._ecu, values=[e["name"] for e in ECU_CATALOG], width=180).grid(row=0, column=1, padx=8)
        ctk.CTkLabel(controls, text="Target firmware", text_color=COLORS["text_muted"]).grid(row=0, column=2, padx=12, sticky="w")
        ctk.CTkOptionMenu(controls, variable=self._ver, values=["v1.1", "v1.2"], width=100).grid(row=0, column=3, padx=8)
        ctk.CTkButton(controls, text="Start OTA deployment", command=self._start).grid(row=0, column=4, padx=16)

        self._hero = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=12)
        self._hero.pack(fill="x", padx=24, pady=12)
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
        self._stages = ctk.CTkFrame(self._hero, fg_color="transparent")
        self._stages.pack(fill="x", padx=20, pady=8)
        self._status = ctk.CTkLabel(self._hero, text="IDLE", font=ctk.CTkFont(size=16, weight="bold"), text_color=COLORS["text_muted"])
        self._status.pack(anchor="w", padx=20, pady=(4, 16))

        section_title(self, "OTA history").pack(anchor="w", padx=24, pady=(8, 4))
        self._hist = ctk.CTkTextbox(self, height=140, fg_color=COLORS["bg_card"], font=ctk.CTkFont(family="Consolas", size=12))
        self._hist.pack(fill="x", padx=24, pady=(0, 20))

    def _start(self) -> None:
        self.platform.start_ota(self._ecu.get(), self._ver.get())

    def refresh(self) -> None:
        ota = self.platform.snapshot()["ota"]
        self._versions.configure(text=f"Current firmware {ota['current_version']}     Target firmware {ota['target_version']}     ECU {ota['target_ecu']}")
        for child in self._checks.winfo_children():
            child.destroy()
        labels = [
            ("Firmware Validation", ota["checks"].get("firmware_validation")),
            ("Integrity Check", ota["checks"].get("integrity_check")),
            ("Compatibility Check", ota["checks"].get("compatibility_check")),
        ]
        for name, ok in labels:
            mark = "✓" if ok else "○"
            color = COLORS["success"] if ok else COLORS["text_muted"]
            ctk.CTkLabel(self._checks, text=f"{name} {mark}", text_color=color, font=ctk.CTkFont(size=13, weight="bold")).pack(
                side="left", padx=(0, 18)
            )
        self._bar.set((ota.get("progress") or 0) / 100)
        self._pct.configure(text=f"{ota.get('progress') or 0}%")
        for child in self._stages.winfo_children():
            child.destroy()
        pretty = {
            "esp32_gateway": "ESP32 Gateway",
            "stm32_transfer": "STM32 Transfer",
            "ecu_update": "ECU Update",
            "verification": "Verification",
        }
        for key, label in pretty.items():
            st = ota["stages"].get(key, "PENDING")
            mark = "✓" if st == "DONE" else "○"
            color = COLORS["success"] if st == "DONE" else COLORS["text_muted"]
            ctk.CTkLabel(self._stages, text=f"{label} {mark}", text_color=color, font=ctk.CTkFont(size=13, weight="bold")).pack(
                side="left", padx=(0, 16)
            )
        status = ota.get("status") or "IDLE"
        result = ota.get("result") or status
        color = COLORS["success"] if status == "SUCCESS" else COLORS["warning"] if status not in {"IDLE"} else COLORS["text_muted"]
        extra = ""
        if status == "SUCCESS":
            extra = f"    {self.platform.snapshot()['firmware']} ← update applied in vehicle state"
        self._status.configure(text=f"STATUS: {result}{extra}", text_color=color)

        self._hist.delete("1.0", "end")
        rows = self.platform.history.query_ota()
        if not rows:
            self._hist.insert("end", "No completed deployments yet.\n")
            return
        for row in rows:
            self._hist.insert(
                "end",
                f"{row['timestamp'][11:19]}   {row['target_ecu']:<16}  {row['from_version']} → {row['to_version']}   {row['result']}\n",
            )
