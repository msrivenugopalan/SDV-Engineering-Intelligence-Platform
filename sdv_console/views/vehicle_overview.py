"""Vehicle Overview (architecture doc §5A) — system-level summary only.
Aggregates existing Central State; generates nothing of its own. OTA, CAN,
Fault Injection, Diagnostics, ARI, and Voice each have their own full page
reachable from the sidebar — this page does not duplicate them.
"""

from __future__ import annotations

import customtkinter as ctk

from sdv_console.components.digital_twin import DigitalTwin
from sdv_console.components.widgets import ECUTile, MetricTile, PanelCard, SparklineCanvas, format_uptime, status_color
from sdv_console.config import COLORS


class VehicleOverviewView(ctk.CTkFrame):
    def __init__(self, master, platform, **kwargs) -> None:
        super().__init__(master, fg_color=COLORS["bg_primary"], corner_radius=0, **kwargs)
        self.platform = platform
        self._metrics: dict[str, MetricTile] = {}
        self._ecu_tiles: dict[str, ECUTile] = {}
        self._sparks: dict[str, SparklineCanvas] = {}
        self._spark_vals: dict[str, ctk.CTkLabel] = {}
        self._build()

    def _build(self) -> None:
        self.grid_rowconfigure(1, weight=3)
        self.grid_rowconfigure(2, weight=2)
        self.grid_columnconfigure(0, weight=1)

        head = ctk.CTkFrame(self, fg_color="transparent")
        head.grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 4))
        ctk.CTkLabel(head, text="VEHICLE OVERVIEW", font=ctk.CTkFont(family="Segoe UI", size=16, weight="bold"), text_color=COLORS["text_primary"]).pack(side="left")
        self._mode_badge = ctk.CTkLabel(head, text="", font=ctk.CTkFont(family="Consolas", size=11, weight="bold"))
        self._mode_badge.pack(side="right")

        row1 = ctk.CTkFrame(self, fg_color="transparent")
        row1.grid(row=1, column=0, sticky="nsew", padx=10, pady=4)
        for i, w in enumerate((3, 5, 4)):
            row1.grid_columnconfigure(i, weight=w)
        row1.grid_rowconfigure(0, weight=1)

        self._build_health(row1).grid(row=0, column=0, sticky="nsew", padx=4)
        twin_card = PanelCard(row1, title="Digital Twin", subtitle="Live ECU mapping · full view on Digital Twin page")
        twin_card.grid(row=0, column=1, sticky="nsew", padx=4)
        for c in twin_card.body.winfo_children():
            c.destroy()
        self._twin = DigitalTwin(twin_card.body, self.platform.snapshot, compact=True)
        self._twin.pack(fill="both", expand=True)
        self._build_telemetry(row1).grid(row=0, column=2, sticky="nsew", padx=4)

        row2 = ctk.CTkFrame(self, fg_color="transparent")
        row2.grid(row=2, column=0, sticky="nsew", padx=10, pady=(4, 6))
        row2.grid_columnconfigure(0, weight=1)
        row2.grid_rowconfigure(0, weight=1)
        self._build_ecus(row2).grid(row=0, column=0, sticky="nsew", padx=4)

        footer = ctk.CTkFrame(self, fg_color="transparent")
        footer.grid(row=3, column=0, sticky="ew", padx=18, pady=(0, 10))
        ctk.CTkLabel(
            footer,
            text="OTA, CAN/DBC, Fault Injection, Diagnostics, Autonomous Recovery, ARI, and Voice each have their own page — use the sidebar.",
            font=ctk.CTkFont(size=10), text_color=COLORS["text_muted"],
        ).pack(anchor="w")

    def _build_health(self, parent) -> PanelCard:
        card = PanelCard(parent, title="Vehicle Health", subtitle="Primary metrics")
        self._health_status = ctk.CTkLabel(card.body, text="—", font=ctk.CTkFont(family="Consolas", size=22, weight="bold"))
        self._health_status.pack(anchor="w", pady=(0, 6))
        grid = ctk.CTkFrame(card.body, fg_color="transparent")
        grid.pack(fill="x")
        for i in range(2):
            grid.grid_columnconfigure(i, weight=1)
        for i, (key, label, unit) in enumerate([("speed", "Speed", "km/h"), ("soc", "Battery SoC", "%"), ("range", "Range", "km"), ("power", "Power", "W")]):
            tile = MetricTile(grid, label, "—", unit)
            tile.grid(row=i // 2, column=i % 2, sticky="nsew", padx=2, pady=2)
            self._metrics[key] = tile
        self._health_meta = ctk.CTkLabel(card.body, text="", font=ctk.CTkFont(family="Consolas", size=10), text_color=COLORS["text_secondary"], justify="left", anchor="w")
        self._health_meta.pack(anchor="w", pady=(8, 0))
        self._firmware_line = ctk.CTkLabel(card.body, text="", font=ctk.CTkFont(family="Consolas", size=10, weight="bold"), text_color=COLORS["accent"], justify="left", anchor="w")
        self._firmware_line.pack(anchor="w", pady=(4, 0))
        return card

    def _build_telemetry(self, parent) -> PanelCard:
        card = PanelCard(parent, title="Live Telemetry", subtitle="Snapshot · full charts on Live Telemetry page")
        for key, label, color in [("vehicle_speed", "Speed", COLORS["accent"]), ("battery_soc", "SoC", COLORS["success"]), ("engine_temp", "Motor °C", COLORS["warning"]), ("battery_voltage", "Voltage", COLORS["mono"])]:
            row = ctk.CTkFrame(card.body, fg_color="transparent")
            row.pack(fill="x", pady=2)
            top = ctk.CTkFrame(row, fg_color="transparent")
            top.pack(fill="x")
            ctk.CTkLabel(top, text=label, font=ctk.CTkFont(size=10), text_color=COLORS["text_muted"]).pack(side="left")
            val = ctk.CTkLabel(top, text="—", font=ctk.CTkFont(family="Consolas", size=11, weight="bold"))
            val.pack(side="right")
            self._spark_vals[key] = val
            spark = SparklineCanvas(row, height=32, color=color)
            spark.pack(fill="x")
            self._sparks[key] = spark
        return card

    def _build_ecus(self, parent) -> PanelCard:
        card = PanelCard(parent, title="Virtual ECUs", subtitle="FreeRTOS task map · detail on Virtual ECUs page")
        grid = ctk.CTkFrame(card.body, fg_color="transparent")
        grid.pack(fill="both", expand=True)
        for i in range(6):
            grid.grid_columnconfigure(i, weight=1)
        for i, ecu_id in enumerate(["engine", "battery", "brake", "steering", "climate", "adas"]):
            tile = ECUTile(grid)
            tile.grid(row=0, column=i, sticky="nsew", padx=3, pady=2)
            self._ecu_tiles[ecu_id] = tile
        return card

    def refresh(self) -> None:
        snap = self.platform.snapshot()
        tel = snap["telemetry"]
        hist = snap["telemetry_history"]

        self._mode_badge.configure(text=snap["connection_label"], text_color=status_color(snap["mode"]) if snap["mode"] == "HARDWARE" else COLORS["warning"] if snap["mode"] == "SIMULATION" else COLORS["error"])
        health = snap["overall_health"]
        self._health_status.configure(text=health, text_color=status_color(health))
        self._metrics["speed"].set(f"{tel.get('vehicle_speed', 0):.1f}")
        self._metrics["soc"].set(f"{tel.get('battery_soc', 0):.1f}", color=COLORS["success"] if tel.get("battery_soc", 0) > 30 else COLORS["error"])
        self._metrics["range"].set(f"{tel.get('estimated_range', 0):.0f}")
        self._metrics["power"].set(f"{tel.get('battery_power', 0):.1f}")

        online = sum(1 for e in snap["ecus"].values() if e["status"] != "OFFLINE")
        self._health_meta.configure(text=f"Faults {len(snap['active_faults'])}   ECUs online {online}/6\nUptime {format_uptime(snap['uptime_started'])}   State {tel.get('vehicle_state', '—')}")

        fw = snap["firmware"]
        ota = snap["ota"]
        if ota.get("status") == "COMPLETED" and ota.get("target_version") == fw:
            self._firmware_line.configure(text=f"Firmware {fw}  ·  \u2191 just updated via OTA ({ota.get('target_ecu', '')})", text_color=COLORS["success"])
        else:
            self._firmware_line.configure(text=f"Firmware {fw}", text_color=COLORS["accent"])

        self._twin.refresh()

        units = {"vehicle_speed": (" km/h", 1), "battery_soc": (" %", 1), "engine_temp": (" °C", 1), "battery_voltage": (" V", 2)}
        for key, spark in self._sparks.items():
            fmt = units.get(key, ("", 1))
            cur = tel.get(key)
            self._spark_vals[key].configure(text=f"{cur:.{fmt[1]}f}{fmt[0]}" if isinstance(cur, (int, float)) else str(cur))
            spark.draw(hist.get(key, []))

        for ecu_id, tile in self._ecu_tiles.items():
            if ecu_id in snap["ecus"]:
                tile.update_from(snap["ecus"][ecu_id])
