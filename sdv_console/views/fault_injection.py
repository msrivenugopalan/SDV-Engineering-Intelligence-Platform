"""Fault Injection (architecture doc §10). Engineer → select ECU → select
fault → Central State → ECU state changes → Diagnostics → Digital Twin →
ARI → Voice → Recovery. One click here ripples through every other page.
"""

from __future__ import annotations

import customtkinter as ctk

from sdv_console.components.widgets import caption, section_title
from sdv_console.config import COLORS, ECU_CATALOG, FAULT_CATALOG


class FaultInjectionView(ctk.CTkFrame):
    def __init__(self, master, platform, **kwargs) -> None:
        super().__init__(master, fg_color=COLORS["bg_primary"], corner_radius=0, **kwargs)
        self.platform = platform
        self._ecu_by_label = {e["name"]: e["id"] for e in ECU_CATALOG}
        self._ecu_by_label["Communication"] = "communication"
        self._ecu_choice = ctk.StringVar(value="Battery ECU")
        self._build()

    def _build(self) -> None:
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=24, pady=16)
        section_title(head, "Fault Injection").pack(anchor="w")
        caption(head, "Possible demonstration faults: battery over-temperature, motor over-temperature, communication failure, "
                       "sensor failure, ECU unavailable, voltage abnormality. Limited to what the simulator actually models.").pack(anchor="w")

        controls = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=10)
        controls.pack(fill="x", padx=24, pady=8)
        ctk.CTkLabel(controls, text="Target ECU", text_color=COLORS["text_muted"]).grid(row=0, column=0, padx=12, pady=16, sticky="w")
        ctk.CTkOptionMenu(controls, variable=self._ecu_choice, values=list(self._ecu_by_label.keys()), width=200).grid(row=0, column=1, padx=8)
        ctk.CTkButton(controls, text="INJECT FAULT", fg_color=COLORS["error"], hover_color="#B91C1C", command=self._inject).grid(row=0, column=2, padx=16)
        self._result = ctk.CTkLabel(controls, text="", font=ctk.CTkFont(size=11), text_color=COLORS["text_muted"])
        self._result.grid(row=0, column=3, padx=12, sticky="w")

        section_title(self, "Fault Catalog").pack(anchor="w", padx=24, pady=(12, 4))
        table = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=8)
        table.pack(fill="x", padx=24, pady=(0, 12))
        for i, h in enumerate(["ECU", "Fault ID", "Severity"]):
            table.grid_columnconfigure(i, weight=1)
            ctk.CTkLabel(table, text=h, font=ctk.CTkFont(size=10, weight="bold"), text_color=COLORS["text_muted"]).grid(row=0, column=i, sticky="w", padx=8, pady=(10, 4))
        for r, (ecu_id, spec) in enumerate(FAULT_CATALOG.items(), start=1):
            ctk.CTkLabel(table, text=ecu_id, font=ctk.CTkFont(family="Consolas", size=11)).grid(row=r, column=0, sticky="w", padx=8, pady=2)
            ctk.CTkLabel(table, text=spec["fault_id"], font=ctk.CTkFont(family="Consolas", size=11)).grid(row=r, column=1, sticky="w", padx=8, pady=2)
            sev_color = COLORS["error"] if spec["severity"] == "CRITICAL" else COLORS["warning"] if spec["severity"] == "WARNING" else COLORS["text_muted"]
            ctk.CTkLabel(table, text=spec["severity"], font=ctk.CTkFont(family="Consolas", size=11, weight="bold"), text_color=sev_color).grid(row=r, column=2, sticky="w", padx=8, pady=2)

        section_title(self, "Active Faults").pack(anchor="w", padx=24, pady=(8, 4))
        self._active_box = ctk.CTkTextbox(self, height=140, fg_color=COLORS["bg_card"], font=ctk.CTkFont(family="Consolas", size=12))
        self._active_box.pack(fill="x", padx=24, pady=(0, 24))

    def _inject(self) -> None:
        ecu_id = self._ecu_by_label.get(self._ecu_choice.get(), "battery")
        res = self.platform.inject_fault(ecu_id)
        if res.get("ok"):
            self._result.configure(text=f"Injected {res.get('fault_id')} \u2192 twin / diagnostics / ARI", text_color=COLORS["warning"])
        else:
            self._result.configure(text=str(res), text_color=COLORS["error"])

    def refresh(self) -> None:
        faults = self.platform.snapshot()["active_faults"]
        self._active_box.delete("1.0", "end")
        if not faults:
            self._active_box.insert("end", "No active faults. Inject one above to see it propagate across the console.\n")
            return
        for f in faults:
            self._active_box.insert("end", f"{f['ecu']:<14} {f.get('fault_id', '—'):<22} {f['status']}\n")
