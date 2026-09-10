"""Voice Assistant — typed input plus optional microphone input and spoken replies."""

from __future__ import annotations

import threading

import customtkinter as ctk

try:
    import pyttsx3
except Exception:  # pragma: no cover - optional dependency
    pyttsx3 = None

try:
    import speech_recognition as sr
except Exception:  # pragma: no cover - optional dependency
    sr = None

from sdv_console.components.widgets import caption, section_title
from sdv_console.config import COLORS


class VoiceView(ctk.CTkFrame):
    def __init__(self, master, platform, **kwargs) -> None:
        super().__init__(master, fg_color=COLORS["bg_primary"], corner_radius=0, **kwargs)
        self.platform = platform
        self._stamp = None
        self._busy = False

        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=24, pady=16)
        section_title(head, "Voice Assistant").pack(anchor="w")
        caption(head, "Ask free-form system questions or use the microphone button for spoken input. The assistant answers from live console state and can speak replies back with text-to-speech when available.").pack(anchor="w")

        entry_row = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=10)
        entry_row.pack(fill="x", padx=24, pady=8)

        self._entry = ctk.CTkEntry(entry_row, placeholder_text="Type a command or question…", height=36)
        self._entry.pack(side="left", fill="x", expand=True, padx=16, pady=16)
        self._entry.bind("<Return>", lambda _e: self._send())

        ctk.CTkButton(entry_row, text="Send", width=90, height=36, command=self._send).pack(side="left", padx=(0, 16))

        self._listen_btn = ctk.CTkButton(entry_row, text="🎙 Listen", width=110, height=36, command=self._listen_and_send)
        self._listen_btn.pack(side="left", padx=(0, 8))

        self._speak_btn = ctk.CTkButton(entry_row, text="🔊 Speak Reply", width=120, height=36, command=self._speak_reply)
        self._speak_btn.pack(side="left", padx=(0, 16))

        self._status = ctk.CTkLabel(entry_row, text="Voice ready", font=ctk.CTkFont(size=10), text_color=COLORS["text_muted"])
        self._status.pack(side="left", padx=(0, 16))

        reply_card = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=10)
        reply_card.pack(fill="x", padx=24, pady=8)
        self._reply = ctk.CTkLabel(reply_card, text="Ready.", font=ctk.CTkFont(size=13), text_color=COLORS["accent"], wraplength=1100, justify="left", anchor="w")
        self._reply.pack(padx=16, pady=16, anchor="w")

        section_title(self, "Command Log").pack(anchor="w", padx=24, pady=(8, 4))
        self._log = ctk.CTkTextbox(self, fg_color=COLORS["bg_card"], font=ctk.CTkFont(family="Consolas", size=12))
        self._log.pack(fill="both", expand=True, padx=24, pady=(0, 24))

    def _set_status(self, text: str) -> None:
        self._status.configure(text=text)

    def _send(self, text: str | None = None) -> None:
        prompt = (text or self._entry.get()).strip()
        if not prompt:
            return

        self._entry.delete(0, "end")
        reply = self.platform.handle_voice(prompt)
        self._reply.configure(text=reply)
        self._speak_reply(reply)

    def _listen_and_send(self) -> None:
        if sr is None:
            self._set_status("Speech recognition package is not installed.")
            return

        if self._busy:
            return

        self._busy = True
        self._listen_btn.configure(state="disabled")
        self._set_status("Listening… speak now")
        threading.Thread(target=self._capture_audio, daemon=True).start()

    def _capture_audio(self) -> None:
        try:
            recognizer = sr.Recognizer()
            recognizer.dynamic_energy_threshold = True
            with sr.Microphone() as source:
                audio = recognizer.listen(source, phrase_time_limit=10, timeout=8)
            try:
                text = recognizer.recognize_google(audio)
            except Exception:
                text = ""

            self.after(0, lambda: self._handle_voice_result(text))
        except Exception as exc:
            self.after(0, lambda: self._handle_voice_result("", exc))

    def _handle_voice_result(self, text: str, error: Exception | None = None) -> None:
        self._busy = False
        self._listen_btn.configure(state="normal")

        if error is not None:
            self._set_status(f"Listening error: {error}")
            return

        if not text:
            self._set_status("No speech detected. Please try again.")
            return

        self._set_status("Voice command captured")
        self._send(text)

    def _speak_reply(self, text: str | None = None) -> None:
        if pyttsx3 is None:
            return

        speech_text = (text or self._reply.cget("text") or "").strip()
        if not speech_text:
            return

        try:
            engine = pyttsx3.init()
            engine.setProperty("rate", 175)
            engine.say(speech_text)
            engine.runAndWait()
        except Exception:
            self._set_status("Voice playback failed")

    def refresh(self) -> None:
        log = self.platform.snapshot()["voice_log"]
        stamp = tuple(entry["timestamp"] for entry in log[:10])
        if stamp == self._stamp:
            return
        self._stamp = stamp
        self._log.delete("1.0", "end")
        if not log:
            self._log.insert("end", "No commands yet.\n")
            return
        for entry in log:
            ts = entry["timestamp"][11:19]
            self._log.insert("end", f"[{ts}] You: {entry['utterance']}\nARI: {entry['reply']}\n\n")
