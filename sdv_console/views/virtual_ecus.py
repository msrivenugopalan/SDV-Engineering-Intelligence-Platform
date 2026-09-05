"""Virtual ECU page — FreeRTOS task mapping and live task/ECU state."""

import customtkinter as ctk

from sdv_console.components.widgets import caption, section_title, status_color
from sdv_console.config import COLORS, SYSTEM_TASKS
from sdv_console.platform import EngineeringPlatform


class VirtualECUView(ctk.CTkScrollableFrame):
    def __init__(self, master, platform: EngineeringPlatform, **kwargs) -> None:
        super().__init__(master, fg_color=COLORS["bg_primary"], corner_radius=0, **kwargs)
        self.platform = platform
        self._rows: dict[str, dict] = {}
        self._build()

    def _build(self) -> None:
        box = ctk.CTkFrame(self, fg_color="transparent")
        box.pack(fill="x", padx=24, pady=16)
        section_title(box, "Virtual ECUs").pack(anchor="w")
        caption(
            box,
            "Each ECU is a FreeRTOS task on the STM32 Nucleo-F446RE. Simulation runs the same logical tasks in software "
            "so the console can be demonstrated before the MCU is attached.",
        ).pack(anchor="w", pady=(0, 12))

        self._table = ctk.CTkFrame(self, fg_color=COLORS["bg_card"], corner_radius=10)
        self._table.pack(fill="both", expand=True, padx=24, pady=(0, 12))
        headers = ["ECU / Task", "ECU state", "Task state", "Telemetry", "Fault", "Last event"]
        for i, h in enumerate(headers):
            ctk.CTkLabel(self._table, text=h, font=ctk.CTkFont(size=11, weight="bold"), text_color=COLORS["text_muted"]).grid(
                row=0, column=i, sticky="w", padx=10, pady=8
            )
            self._table.grid_columnconfigure(i, weight=1)

        for ecu_id in ["engine", "battery", "brake", "steering", "climate", "adas"]:
            self._rows[ecu_id] = self._add_row(len(self._rows) + 1)

        sys_box = ctk.CTkFrame(self, fg_color="transparent")
        sys_box.pack(fill="x", padx=24, pady=(8, 20))
        section_title(sys_box, "System-level FreeRTOS tasks").pack(anchor="w")
        for task in SYSTEM_TASKS:
            line = ctk.CTkFrame(sys_box, fg_color=COLORS["bg_card"], corner_radius=8)
            line.pack(fill="x", pady=4)
            ctk.CTkLabel(line, text=task["task_name"], font=ctk.CTkFont(size=13, weight="bold"), text_color=COLORS["accent_blueprint"]).pack(
                side="left", padx=12, pady=10
            )
            ctk.CTkLabel(line, text=task["responsibility"], font=ctk.CTkFont(size=12), text_color=COLORS["text_secondary"]).pack(
                side="left", padx=8
            )

    def _add_row(self, row: int) -> dict:
        widgets = {}
        keys = ["name", "status", "task", "tel", "fault", "event"]
        for col, key in enumerate(keys):
            label = ctk.CTkLabel(self._table, text="—", font=ctk.CTkFont(size=12), text_color=COLORS["text_primary"], anchor="w")
            label.grid(row=row, column=col, sticky="w", padx=10, pady=6)
            widgets[key] = label
        return widgets

    def refresh(self) -> None:
        snap = self.platform.snapshot()
        tel = snap["telemetry"]
        snippets = {
            "engine": f"{tel.get('engine_temp')} C",
            "battery": f"{tel.get('battery_voltage')} V",
            "brake": str(tel.get("brake_status")),
            "steering": str(tel.get("steering_status")),
            "climate": f"{tel.get('cabin_temp')} C",
            "adas": str(tel.get("adas_status")),
        }
        for ecu_id, widgets in self._rows.items():
            ecu = snap["ecus"][ecu_id]
            widgets["name"].configure(text=f"{ecu['name']}\n{ecu['task_name']}")
            widgets["status"].configure(text=ecu["status"], text_color=status_color(ecu["status"]))
            widgets["task"].configure(text=ecu["task_state"])
            widgets["tel"].configure(text=snippets.get(ecu_id, "—"))
            widgets["fault"].configure(text=ecu.get("fault_id") or "none")
            widgets["event"].configure(text=ecu.get("last_event") or "—")
