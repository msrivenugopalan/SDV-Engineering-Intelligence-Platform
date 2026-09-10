"""Content panel — the page switcher. All views are built once at startup
and swapped with tkraise() (cheap), not rebuilt on navigation (expensive).
Only the currently visible view's refresh() runs each tick.
"""

from __future__ import annotations

import customtkinter as ctk

from sdv_console.config import COLORS
from sdv_console.views.ari import ARIView
from sdv_console.views.can_monitor import CANMonitorView
from sdv_console.views.digital_twin_view import DigitalTwinView
from sdv_console.views.diagnostics import DiagnosticsView
from sdv_console.views.fault_injection import FaultInjectionView
from sdv_console.views.history import HistoryView
from sdv_console.views.ota import OTAManagerView
from sdv_console.views.recovery import RecoveryView
from sdv_console.views.settings import SettingsView
from sdv_console.views.system_logs import SystemLogsView
from sdv_console.views.telemetry import TelemetryView
from sdv_console.views.vehicle_overview import VehicleOverviewView
from sdv_console.views.virtual_ecus import VirtualECUsView
from sdv_console.views.voice import VoiceView

VIEW_MAP = {
    "overview": VehicleOverviewView,
    "telemetry": TelemetryView,
    "ecus": VirtualECUsView,
    "twin": DigitalTwinView,
    "can": CANMonitorView,
    "ota": OTAManagerView,
    "diagnostics": DiagnosticsView,
    "fault": FaultInjectionView,
    "recovery": RecoveryView,
    "logs": SystemLogsView,
    "ari": ARIView,
    "voice": VoiceView,
    "history": HistoryView,
    "settings": SettingsView,
}


class ContentPanel(ctk.CTkFrame):
    def __init__(self, master, platform, **kwargs) -> None:
        super().__init__(master, fg_color=COLORS["bg_primary"], corner_radius=0, **kwargs)
        self.platform = platform
        self._views: dict[str, ctk.CTkFrame] = {}
        self._active = "overview"
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        for route, cls in VIEW_MAP.items():
            view = cls(self, platform)
            view.grid(row=0, column=0, sticky="nsew")
            self._views[route] = view

        self.show("overview")

    def show(self, route: str) -> None:
        if route not in self._views:
            return
        self._active = route
        for key, view in self._views.items():
            view.grid_remove() if key != route else view.grid()
        self._views[route].tkraise()
        self.refresh_active()

    def refresh_active(self) -> None:
        view = self._views.get(self._active)
        if view is not None and hasattr(view, "refresh"):
            view.refresh()
