"""Autonomous Recovery (architecture doc §12). Fault -> Fault Manager ->
Classify -> Recovery Strategy -> Attempt -> Verify -> Recovered/Failed.
"""

from __future__ import annotations

import customtkinter as ctk

from sdv_console.components.widgets import caption, section_title, status_color
from sdv_console.config import COLORS


class RecoveryView(ctk.CTkFrame):
    def __init__(self, master, platform, **kwargs) -> None:
        super().__init__(master, fg_color=COLORS["bg_primary"], corner_radius=0, **kwargs)
        self.platform = platform
        self._stamp = None
        self._build()

    def _build(self) -> None:
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=24, pady=16)
        section_title(head, "Autonomous Recovery").pack(anchor="w")
        caption(head, "FAULT DETECTED \u2192 RECOVERY ACTIVE \u2192 RECOVERY SUCCESSFUL. Pick a faulted ECU below and start recovery; "
                       "the ECU, Diagnostics, and Digital Twin all update from the same event when it completes.").pack(anchor="w")

        self._picker_row = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=10)
        self._picker_row.pack(fill="x", padx=24, pady=8)
        ctk.CTkLabel(self._picker_row, text="Faulted ECU", text_color=COLORS["text_muted"]).grid(row=0, column=0, padx=12, pady=16, sticky="w")
        self._ecu_choice = ctk.StringVar(value="—")
        self._menu = ctk.CTkOptionMenu(self._picker_row, variable=self._ecu_choice, values=["—"], width=200)
        self._menu.grid(row=0, column=1, padx=8)
        ctk.CTkButton(self._picker_row, text="START RECOVERY", fg_color=COLORS["accent_muted"], hover_color=COLORS["accent_glow"], command=self._start).grid(row=0, column=2, padx=16)
        self._result = ctk.CTkLabel(self._picker_row, text="", font=ctk.CTkFont(size=11), text_color=COLORS["text_muted"])
        self._result.grid(row=0, column=3, padx=12, sticky="w")

        self._banner = ctk.CTkFrame(self, fg_color=COLORS["success"], corner_radius=10)
        self._banner_label = ctk.CTkLabel(self._banner, text="", font=ctk.CTkFont(size=14, weight="bold"), text_color="#052E16")
        self._banner_label.pack(padx=16, pady=10, anchor="w")
        self._banner_visible = False

        self._status_card = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=10)
        self._status_card.pack(fill="x", padx=24, pady=8)
        self._status_label = ctk.CTkLabel(self._status_card, text="IDLE — no recovery in progress", font=ctk.CTkFont(family="Consolas", size=14, weight="bold"), text_color=COLORS["text_muted"])
        self._status_label.pack(anchor="w", padx=16, pady=16)

        section_title(self, "Recovery Stages").pack(anchor="w", padx=24, pady=(8, 4))
        stages = ctk.CTkFrame(self, fg_color="transparent")
        stages.pack(fill="x", padx=24, pady=(0, 24))
        self._stage_labels = []
        for label in ["FAULT DETECTED", "CLASSIFY", "RECOVERY ACTIVE", "VERIFY", "RECOVERED"]:
            lbl = ctk.CTkLabel(stages, text=label, font=ctk.CTkFont(size=11, weight="bold"), text_color=COLORS["text_muted"])
            lbl.pack(side="left", padx=(0, 24))
            self._stage_labels.append(lbl)

    def _start(self) -> None:
        label = self._ecu_choice.get()
        if label == "—":
            return
        ecu_id = self._ecu_by_label.get(label)
        if not ecu_id:
            return
        res = self.platform.start_recovery(ecu_id)
        self._result.configure(text=str(res) if not res.get("ok") else "Recovery started…", text_color=COLORS["warning"])

    def refresh(self) -> None:
        snap = self.platform.snapshot()
        faults = snap["active_faults"]
        self._ecu_by_label = {}
        for f in faults:
            label = f"{f['name']} ({f.get('fault_id')})"
            self._ecu_by_label[label] = f["ecu"]
        values = list(self._ecu_by_label.keys()) or ["—"]
        self._menu.configure(values=values)
        if self._ecu_choice.get() not in values:
            self._ecu_choice.set(values[0])

        rec = snap["recovery"]
        status = rec.get("status", "IDLE")
        stamp = (status, rec.get("ecu"))
        if stamp == self._stamp:
            return
        self._stamp = stamp

        colors = {"IDLE": COLORS["text_muted"], "ACTIVE": COLORS["warning"], "SUCCESS": COLORS["success"], "FAILED": COLORS["error"]}
        texts = {
            "IDLE": "IDLE — no recovery in progress",
            "ACTIVE": f"RECOVERY ACTIVE on {rec.get('ecu', '—')} — classifying fault, attempting recovery…",
            "SUCCESS": f"RECOVERY SUCCESSFUL — {rec.get('ecu', '—')} restored to HEALTHY",
            "FAILED": f"RECOVERY FAILED on {rec.get('ecu', '—')}",
        }
        self._status_label.configure(text=texts.get(status, status), text_color=colors.get(status, COLORS["text_muted"]))

        active_stage = {"IDLE": -1, "ACTIVE": 2, "SUCCESS": 4, "FAILED": 3}.get(status, -1)
        for i, lbl in enumerate(self._stage_labels):
            lbl.configure(text_color=COLORS["success"] if i <= active_stage else COLORS["text_muted"])

        if status == "SUCCESS":
            if not self._banner_visible:
                self._banner.pack(fill="x", padx=24, pady=(0, 8), before=self._status_card)
                self._banner_visible = True
            self._banner_label.configure(text=f"\u2713  {rec.get('ecu', 'ECU')} RECOVERED — status restored to HEALTHY, diagnostic cleared")
        elif self._banner_visible and status != "SUCCESS":
            self._banner.pack_forget()
            self._banner_visible = False
