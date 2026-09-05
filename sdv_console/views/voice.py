"""Voice engineering assistant — allow-listed commands + confirmation."""

import customtkinter as ctk

from sdv_console.components.widgets import caption, section_title
from sdv_console.config import COLORS
from sdv_console.platform import EngineeringPlatform

EXAMPLES = [
    "Show vehicle status.",
    "Show battery status.",
    "What is the current battery voltage?",
    "Inject a brake fault.",
    "Confirm.",
    "Show active faults.",
    "Start recovery.",
    "What happened to the brake ECU?",
    "Show CAN traffic.",
    "Start OTA deployment.",
]


class VoiceAssistantView(ctk.CTkFrame):
    def __init__(self, master, platform: EngineeringPlatform, **kwargs) -> None:
        super().__init__(master, fg_color=COLORS["bg_primary"], corner_radius=0, **kwargs)
        self.platform = platform
        self._build()

    def _build(self) -> None:
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=24, pady=16)
        section_title(head, "Voice Engineering Assistant").pack(anchor="w")
        caption(
            head,
            "Hands-free interface for the console. Speech (or typed text) is parsed against an allow-list. "
            "Fault injection and OTA require an explicit Confirm. No paid AI API is used.",
        ).pack(anchor="w")

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=24, pady=8)
        self._entry = ctk.CTkEntry(row, placeholder_text="Type an engineering command…", height=40)
        self._entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        self._entry.bind("<Return>", lambda _e: self._send())
        ctk.CTkButton(row, text="Send", width=90, command=self._send).pack(side="left", padx=4)
        ctk.CTkButton(row, text="Confirm", width=90, command=lambda: self._run("confirm")).pack(side="left", padx=4)
        ctk.CTkButton(row, text="Cancel", width=90, fg_color=COLORS["bg_card"], command=lambda: self._run("cancel")).pack(side="left")

        self._reply = ctk.CTkLabel(self, text="Ready.", font=ctk.CTkFont(size=14), text_color=COLORS["accent_blueprint"], wraplength=1000, justify="left")
        self._reply.pack(anchor="w", padx=24, pady=8)

        section_title(self, "Supported commands").pack(anchor="w", padx=24, pady=(12, 4))
        for ex in EXAMPLES:
            ctk.CTkLabel(self, text=f"•  {ex}", text_color=COLORS["text_secondary"], font=ctk.CTkFont(size=13)).pack(anchor="w", padx=32)

        caption(
            self,
            "Optional microphone: install SpeechRecognition + a local mic backend later. Typed commands are the reliable demo path.",
        ).pack(anchor="w", padx=24, pady=16)

    def _send(self) -> None:
        self._run(self._entry.get())

    def _run(self, text: str) -> None:
        result = self.platform.handle_voice(text)
        self._reply.configure(text=result.get("reply") or str(result))
        if text.lower() not in {"confirm", "cancel"}:
            self._entry.delete(0, "end")

    def refresh(self) -> None:
        return
