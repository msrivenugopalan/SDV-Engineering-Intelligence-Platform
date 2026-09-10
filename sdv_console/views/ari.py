"""ARI Assistant (architecture doc §14) — an engineering intelligence layer,
not a chatbot. Every line here traces to a real Central State field.
"""

from __future__ import annotations

import customtkinter as ctk

from sdv_console.components.widgets import caption, section_title
from sdv_console.config import COLORS


class ARIView(ctk.CTkFrame):
    def __init__(self, master, platform, **kwargs) -> None:
        super().__init__(master, fg_color=COLORS["bg_primary"], corner_radius=0, **kwargs)
        self.platform = platform
        self._stamp = None
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=24, pady=16)
        section_title(head, "ARI Assistant").pack(anchor="w")
        caption(head, "Consumes Central State + Telemetry + Diagnostics + Faults + OTA + ECU State + History, and produces "
                       "engineering insight. ARI never invents a vehicle condition — every line below traces to a real event.").pack(anchor="w")

        summary_card = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=10)
        summary_card.pack(fill="x", padx=24, pady=8)
        self._summary = ctk.CTkLabel(summary_card, text="", font=ctk.CTkFont(size=13), text_color=COLORS["text_primary"], wraplength=1100, justify="left", anchor="w")
        self._summary.pack(padx=16, pady=16, anchor="w")

        section_title(self, "Insight Log").pack(anchor="w", padx=24, pady=(8, 4))
        self._log = ctk.CTkTextbox(self, fg_color=COLORS["bg_card"], font=ctk.CTkFont(family="Consolas", size=12))
        self._log.pack(fill="both", expand=True, padx=24, pady=(0, 24))

    def refresh(self) -> None:
        self._summary.configure(text=self.platform.ari.explain_current_state())
        log = self.platform.snapshot()["ari_log"]
        stamp = tuple(log[:5])
        if stamp == self._stamp:
            return
        self._stamp = stamp
        self._log.delete("1.0", "end")
        if not log:
            self._log.insert("end", "No insights yet — inject a fault, run OTA, or connect hardware to generate one.\n")
            return
        for line in log:
            self._log.insert("end", f"\u2022 {line}\n\n")
