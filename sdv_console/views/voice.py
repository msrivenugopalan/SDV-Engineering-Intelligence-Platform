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

try:
    import sounddevice as sd
except Exception:  # pragma: no cover - optional dependency
    sd = None

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

        self._status = ctk.CTkLabel(entry_row, text="READY", font=ctk.CTkFont(size=10), text_color=COLORS["text_muted"])
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
        self._set_status("EXECUTING")
        try:
            reply = self.platform.handle_voice(prompt)
        except Exception as exc:
            self._reply.configure(text=f"Command failed: {exc}")
            self._set_status("ERROR")
            return
        self._reply.configure(text=reply)
        self._set_status("RESPONSE READY")
        self._speak_reply(reply)

    def _listen_and_send(self) -> None:
        if sr is None or sd is None:
            self._set_status("ERROR: Speech or microphone package is unavailable.")
            return

        if self._busy:
            return

        self._busy = True
        self._listen_btn.configure(state="disabled")
        self._set_status("LISTENING: speak now (up to 6 seconds)")
        threading.Thread(target=self._capture_audio, daemon=True).start()

    def _capture_audio(self) -> None:
        try:
            recognizer = sr.Recognizer()
            device = sd.query_devices(kind="input")
            sample_rate = int(device["default_samplerate"])
            block_size = 1024
            frames_remaining = sample_rate * 6
            chunks = []
            with sd.RawInputStream(
                samplerate=sample_rate,
                channels=1,
                dtype="int16",
                blocksize=block_size,
            ) as stream:
                while frames_remaining:
                    frame_count = min(block_size, frames_remaining)
                    chunk, _overflowed = stream.read(frame_count)
                    chunks.append(chunk)
                    frames_remaining -= frame_count
            audio = sr.AudioData(b"".join(chunks), sample_rate, 2)
            self.after(0, lambda: self._set_status("PROCESSING: recognizing speech"))
            text = recognizer.recognize_google(audio)
            self.after(0, lambda: self._handle_voice_result(text))
        except Exception as exc:
            self.after(0, lambda error=exc: self._handle_voice_result("", error))

    def _handle_voice_result(self, text: str, error: Exception | None = None) -> None:
        self._busy = False
        self._listen_btn.configure(state="normal")

        if error is not None:
            if sr is not None and isinstance(error, sr.UnknownValueError):
                self._set_status("ERROR: Speech was unintelligible.")
            elif sr is not None and isinstance(error, sr.RequestError):
                self._set_status(f"ERROR: Speech recognition unavailable: {error}")
            else:
                self._set_status(f"ERROR: Microphone capture failed: {error}")
            return

        if not text:
            self._set_status("ERROR: No speech detected. Please try again.")
            return

        self._entry.delete(0, "end")
        self._entry.insert(0, text)
        self._set_status("RECOGNIZED")
        self._send(text)

    def _speak_reply(self, text: str | None = None) -> None:
        if pyttsx3 is None:
            self._set_status("ERROR: Text-to-speech package is unavailable.")
            return

        speech_text = (text or self._reply.cget("text") or "").strip()
        if not speech_text:
            return

        threading.Thread(target=self._speak_in_background, args=(speech_text,), daemon=True).start()

    def _speak_in_background(self, speech_text: str) -> None:
        try:
            engine = pyttsx3.init()
            engine.setProperty("rate", 175)
            engine.say(speech_text)
            engine.runAndWait()
        except Exception:
            self.after(0, lambda: self._set_status("ERROR: Voice playback failed."))

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
