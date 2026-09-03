"""Bottom system status bar — honest service flags only."""

import customtkinter as ctk

from sdv_console.config import COLORS
from sdv_console.platform import EngineeringPlatform


class SystemStatusBar(ctk.CTkFrame):
    _DOT = "\u25cf"

    def __init__(self, master, platform: EngineeringPlatform, **kwargs) -> None:
        super().__init__(
            master,
            height=40,
            fg_color=COLORS["bg_header"],
            corner_radius=0,
            **kwargs,
        )
        self.grid_propagate(False)
        self._platform = platform
        self._labels: dict[str, ctk.CTkLabel] = {}
        self._build_layout()
        self.refresh()

    def _build_layout(self) -> None:
        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=16)
        ctk.CTkLabel(
            inner,
            text="SYSTEM STATUS",
            font=ctk.CTkFont(size=10, weight="bold"),
            text_color=COLORS["text_muted"],
        ).pack(side="left", padx=(0, 16))
        for name in ("STM32", "ESP32", "MQTT", "REST API", "SQLite", "Source"):
            frame = ctk.CTkFrame(inner, fg_color="transparent")
            frame.pack(side="left", padx=(0, 18))
            ctk.CTkLabel(frame, text=name, font=ctk.CTkFont(size=11, weight="bold"), text_color=COLORS["text_secondary"]).pack(side="left", padx=(0, 6))
            label = ctk.CTkLabel(frame, text="", font=ctk.CTkFont(size=11), text_color=COLORS["text_muted"])
            label.pack(side="left")
            self._labels[name] = label

    def refresh(self) -> None:
        snap = self._platform.snapshot()
        svc = snap["services"]
        self._set("STM32", "Linked" if svc["stm32"] else "Not linked", svc["stm32"])
        self._set("ESP32", "Linked" if svc["esp32"] else "Not linked", svc["esp32"])
        self._set("MQTT", "Connected" if svc["mqtt"] else "Idle", svc["mqtt"])
        self._set("REST API", "Running" if svc["rest"] else "Stopped", svc["rest"])
        self._set("SQLite", "Ready" if svc["sqlite"] else "Unavailable", svc["sqlite"])
        sim = snap["mode"] == "SIMULATION"
        self._set("Source", "Simulation" if sim else snap["mode"].title(), True if snap["mode"] != "DISCONNECTED" else False)

    def _set(self, name: str, text: str, healthy: bool) -> None:
        color = COLORS["success"] if healthy else COLORS["warning"] if name in {"STM32", "ESP32", "MQTT"} else COLORS["error"]
        if name in {"STM32", "ESP32", "MQTT"} and not healthy:
            color = COLORS["text_muted"]
        self._labels[name].configure(text=f"{self._DOT} {text}", text_color=color)
