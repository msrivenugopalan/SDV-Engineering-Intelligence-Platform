"""Settings / connection status — honest hardware vs simulation."""

import customtkinter as ctk

from sdv_console.components.widgets import caption, section_title
from sdv_console.config import COLORS, MQTT_HOST, REST_HOST, REST_PORT
from sdv_console.platform import EngineeringPlatform


class SettingsView(ctk.CTkScrollableFrame):
    def __init__(self, master, platform: EngineeringPlatform, **kwargs) -> None:
        super().__init__(master, fg_color=COLORS["bg_primary"], corner_radius=0, **kwargs)
        self.platform = platform
        self._info = ctk.CTkLabel(self, text="", justify="left", font=ctk.CTkFont(family="Consolas", size=13), text_color=COLORS["text_primary"])
        self._build()

    def _build(self) -> None:
        head = ctk.CTkFrame(self, fg_color="transparent")
        head.pack(fill="x", padx=24, pady=16)
        section_title(head, "Settings / Connection Status").pack(anchor="w")
        caption(
            head,
            "Simulation is the default so the project can be demonstrated without hardware. "
            "Hardware mode stays disabled until the ESP32/STM32 adapter reports a real link.",
        ).pack(anchor="w")

        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.pack(fill="x", padx=24, pady=8)
        ctk.CTkButton(btns, text="Use SIMULATION MODE", command=lambda: self.platform.set_mode("SIMULATION")).pack(side="left", padx=(0, 8))
        ctk.CTkButton(btns, text="Stop simulation", fg_color=COLORS["bg_card"], command=lambda: self.platform.set_mode("DISCONNECTED")).pack(side="left", padx=8)
        ctk.CTkButton(btns, text="Try HARDWARE MODE", fg_color=COLORS["bg_card"], command=self._try_hw).pack(side="left", padx=8)

        self._msg = ctk.CTkLabel(self, text="", text_color=COLORS["warning"])
        self._msg.pack(anchor="w", padx=24)
        self._info.pack(anchor="w", padx=24, pady=16)

    def _try_hw(self) -> None:
        result = self.platform.set_mode("HARDWARE")
        self._msg.configure(text=result.get("detail") or result.get("error") or "OK")

    def refresh(self) -> None:
        snap = self.platform.snapshot()
        svc = snap["services"]
        self._info.configure(
            text=(
                f"Mode:              {snap['mode']}\n"
                f"Connection label:  {snap['connection_label']}\n"
                f"Firmware:          {snap['firmware']}\n"
                f"STM32 linked:      {svc['stm32']}   (Nucleo-F446RE UART/CAN — not connected)\n"
                f"ESP32 linked:      {svc['esp32']}   (Wi-Fi/MQTT gateway — not connected)\n"
                f"MQTT broker:       {MQTT_HOST or '(not configured)'}\n"
                f"MQTT connected:    {svc['mqtt']}\n"
                f"REST API:          {'http://' + REST_HOST + ':' + str(REST_PORT) if svc['rest'] else 'stopped'}\n"
                f"SQLite:            {svc['sqlite']}\n"
            )
        )
