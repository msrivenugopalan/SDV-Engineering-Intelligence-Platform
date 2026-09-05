"""ARI recovery timeline."""

import customtkinter as ctk

from sdv_console.components.widgets import caption, section_title
from sdv_console.config import COLORS
from sdv_console.platform import EngineeringPlatform

STEP_COLOR = {
    "PENDING": COLORS["offline"],
    "ACTIVE": COLORS["warning"],
    "DONE": COLORS["success"],
    "FAILED": COLORS["error"],
}


class ARIView(ctk.CTkScrollableFrame):
    def __init__(self, master, platform: EngineeringPlatform, **kwargs) -> None:
        super().__init__(master, fg_color=COLORS["bg_primary"], corner_radius=0, **kwargs)
        self.platform = platform
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=24, pady=16)
        section_title(head, "Autonomous Recovery Intelligence (ARI)").pack(anchor="w")
        caption(
            head,
            "Deterministic recovery policy: detect → diagnose → restart the affected ECU task → health check. "
            "This is not a machine-learning controller.",
        ).pack(anchor="w")
        ctk.CTkButton(head, text="Start recovery (if a fault is latched)", width=260, command=self._manual).pack(anchor="w", pady=10)
        self._summary = ctk.CTkLabel(self, text="", font=ctk.CTkFont(size=14, weight="bold"), text_color=COLORS["text_primary"])
        self._summary.pack(anchor="w", padx=24)
        self._steps = ctk.CTkFrame(self, fg_color="transparent")
        self._steps.pack(fill="both", expand=True, padx=24, pady=12)
        self._stamp = None

    def _manual(self) -> None:
        self.platform.start_recovery()

    def refresh(self) -> None:
        ari = self.platform.snapshot()["ari"]
        stamp = (ari["result"], ari.get("correlation_id"), tuple((s["name"], s["status"], s.get("detail")) for s in ari.get("steps") or []))
        if stamp == self._stamp:
            return
        self._stamp = stamp
        if ari["result"] == "IDLE":
            self._summary.configure(text="No recovery session. Inject a fault to start ARI.")
        else:
            self._summary.configure(
                text=f"{ari['fault_id']} on {ari['ecu']}   ·   {ari['result']}",
                text_color=COLORS["success"] if ari["result"] == "SUCCESS" else COLORS["warning"],
            )
        for child in self._steps.winfo_children():
            child.destroy()
        for index, step in enumerate(ari.get("steps") or []):
            row = ctk.CTkFrame(self._steps, fg_color=COLORS["bg_card"], corner_radius=8)
            row.pack(fill="x", pady=4)
            color = STEP_COLOR.get(step["status"], COLORS["text_muted"])
            ctk.CTkLabel(row, text=f"{index + 1}", width=28, font=ctk.CTkFont(size=16, weight="bold"), text_color=color).pack(
                side="left", padx=10, pady=10
            )
            col = ctk.CTkFrame(row, fg_color="transparent")
            col.pack(side="left", fill="x", expand=True)
            ctk.CTkLabel(col, text=step["name"], font=ctk.CTkFont(size=14, weight="bold"), text_color=COLORS["text_primary"]).pack(anchor="w")
            ctk.CTkLabel(col, text=f"{step['status']}  {step.get('detail') or ''}", text_color=color, font=ctk.CTkFont(size=12)).pack(anchor="w")
            if index < len(ari.get("steps") or []) - 1:
                ctk.CTkLabel(self._steps, text="↓", text_color=COLORS["text_muted"]).pack()
