"""Diagnostics panel — explainable rules, not an ML model."""

import customtkinter as ctk

from sdv_console.components.widgets import caption, section_title, status_color
from sdv_console.config import COLORS
from sdv_console.platform import EngineeringPlatform


class DiagnosticsView(ctk.CTkScrollableFrame):
    def __init__(self, master, platform: EngineeringPlatform, **kwargs) -> None:
        super().__init__(master, fg_color=COLORS["bg_primary"], corner_radius=0, **kwargs)
        self.platform = platform
        self._host = ctk.CTkFrame(self, fg_color="transparent")
        self._host.pack(fill="both", expand=True, padx=24, pady=16)
        section_title(self._host, "Diagnostics").pack(anchor="w")
        caption(
            self._host,
            "Rule-based diagnostic engine (thresholds + evidence). Confidence is computed from how far a signal is past its limit. "
            "This is not a trained AI model.",
        ).pack(anchor="w", pady=(0, 12))
        self._cards = ctk.CTkFrame(self._host, fg_color="transparent")
        self._cards.pack(fill="both", expand=True)
        self._stamp = None

    def refresh(self) -> None:
        records = self.platform.snapshot()["diagnostics"]
        stamp = [(r["fault_id"], r["diagnostic_status"], r["recovery_status"], r["confidence"]) for r in records[:12]]
        if stamp == self._stamp:
            return
        self._stamp = stamp
        for child in self._cards.winfo_children():
            child.destroy()
        if not records:
            ctk.CTkLabel(self._cards, text="No diagnostic records yet.", text_color=COLORS["text_muted"]).pack(anchor="w")
            return
        for rec in records[:12]:
            card = ctk.CTkFrame(self._cards, fg_color=COLORS["bg_card"], corner_radius=10)
            card.pack(fill="x", pady=6)
            ctk.CTkLabel(
                card,
                text=f"{rec['fault_id']}   ·   ECU {rec['ecu'].upper()}   ·   {rec['severity']}",
                font=ctk.CTkFont(size=14, weight="bold"),
                text_color=status_color("FAULT" if rec["diagnostic_status"] == "FAULT" else rec["diagnostic_status"]),
            ).pack(anchor="w", padx=14, pady=(10, 2))
            ctk.CTkLabel(card, text=rec["description"], text_color=COLORS["text_primary"], font=ctk.CTkFont(size=12)).pack(anchor="w", padx=14)
            ctk.CTkLabel(card, text=f"Possible cause: {rec['possible_cause']}", text_color=COLORS["text_secondary"], font=ctk.CTkFont(size=12), wraplength=900, justify="left").pack(
                anchor="w", padx=14, pady=2
            )
            evidence = " | ".join(rec.get("evidence") or [])
            ctk.CTkLabel(
                card,
                text=(
                    f"Status: {rec['diagnostic_status']}   Recovery: {rec['recovery_status']}   "
                    f"Confidence: {rec['confidence']}%   Detected: {rec['detected_time']}"
                ),
                text_color=COLORS["text_muted"],
                font=ctk.CTkFont(size=11),
            ).pack(anchor="w", padx=14, pady=(2, 2))
            if evidence:
                ctk.CTkLabel(card, text=f"Evidence: {evidence}", text_color=COLORS["text_muted"], font=ctk.CTkFont(size=11)).pack(
                    anchor="w", padx=14
                )
            ctk.CTkLabel(card, text=f"Recommended: {rec['recommended_action']}", text_color=COLORS["accent_blueprint"], font=ctk.CTkFont(size=12)).pack(
                anchor="w", padx=14, pady=(0, 12)
            )
