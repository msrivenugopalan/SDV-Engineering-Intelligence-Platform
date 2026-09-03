"""Main content host — switches engineering views."""

from __future__ import annotations

import customtkinter as ctk

from sdv_console.config import COLORS
from sdv_console.platform import EngineeringPlatform
from sdv_console.views.ari import ARIView
from sdv_console.views.can_monitor import CANMonitorView
from sdv_console.views.dbc_network import DBCView
from sdv_console.views.diagnostics import DiagnosticsView
from sdv_console.views.digital_twin import DigitalTwinView
from sdv_console.views.fault_injection import FaultInjectionView
from sdv_console.views.history import HistoryView
from sdv_console.views.ota import OTAManagerView
from sdv_console.views.settings import SettingsView
from sdv_console.views.system_logs import SystemLogsView
from sdv_console.views.telemetry import TelemetryView
from sdv_console.views.vehicle_overview import VehicleOverviewView
from sdv_console.views.virtual_ecus import VirtualECUView
from sdv_console.views.voice import VoiceAssistantView


class ContentPanel(ctk.CTkFrame):
    def __init__(self, master: ctk.CTk, platform: EngineeringPlatform, **kwargs) -> None:
        super().__init__(master, fg_color=COLORS["bg_primary"], corner_radius=0, **kwargs)
        self.grid_rowconfigure(0, weight=1)
        self.grid_columnconfigure(0, weight=1)
        self._views: dict[str, ctk.CTkBaseClass] = {}
        self._current = "Vehicle Overview"
        mapping = {
            "Vehicle Overview": VehicleOverviewView,
            "Virtual ECUs": VirtualECUView,
            "Digital Twin": DigitalTwinView,
            "Live Telemetry": TelemetryView,
            "CAN Monitor": CANMonitorView,
            "DBC / Vehicle Network": DBCView,
            "Fault Injection": FaultInjectionView,
            "Diagnostics": DiagnosticsView,
            "Autonomous Recovery": ARIView,
            "OTA Manager": OTAManagerView,
            "Voice Assistant": VoiceAssistantView,
            "Event / Fault History": HistoryView,
            "System Logs": SystemLogsView,
            "Settings": SettingsView,
        }
        for name, cls in mapping.items():
            view = cls(self, platform)
            view.grid(row=0, column=0, sticky="nsew")
            self._views[name] = view
        self.show("Vehicle Overview")

    def show(self, name: str) -> None:
        if name not in self._views:
            name = "Vehicle Overview"
        self._current = name
        self._views[name].tkraise()
        self.refresh_visible()

    def refresh_visible(self) -> None:
        view = self._views.get(self._current)
        if view is not None and hasattr(view, "refresh"):
            view.refresh()
