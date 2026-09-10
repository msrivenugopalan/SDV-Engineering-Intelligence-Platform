"""All constants live here — one place to retune the whole console."""

APP_TITLE = "SDV ENGINEERING CONSOLE"
APP_VERSION = "1.0.0"
WINDOW_WIDTH = 1520
WINDOW_HEIGHT = 920
MIN_WINDOW_WIDTH = 1200
MIN_WINDOW_HEIGHT = 760

TICK_MS = 250  # central state / UI refresh cadence
TELEMETRY_HISTORY_POINTS = 120  # ~30s of rolling history at TICK_MS

REST_HOST = "127.0.0.1"
REST_PORT = 5050

MQTT_HOST = None  # set to a broker host to enable MQTT (paho-mqtt optional dep)
MQTT_PORT = 1883
MQTT_TOPIC_TELEMETRY = "sdv/esp32/telemetry"
MQTT_TOPIC_EVENTS = "sdv/esp32/events"

COLORS = {
    "bg_primary": "#0A0E14",
    "bg_secondary": "#0F1420",
    "bg_card": "#141A26",
    "bg_card_alt": "#1B2333",
    "border": "#232B3D",
    "text_primary": "#E8ECF4",
    "text_secondary": "#9AA5B8",
    "text_muted": "#5C6779",
    "accent": "#3AA0FF",
    "accent_muted": "#1E5A8F",
    "accent_glow": "#5FB6FF",
    "success": "#2ECC71",
    "warning": "#F5A623",
    "error": "#E74C3C",
    "intelligence": "#B084F5",
    "mono": "#7FD8C4",
    "offline": "#3A4258",
}

STATUS_COLORS = {
    "HEALTHY": COLORS["success"],
    "RUNNING": COLORS["success"],
    "WARNING": COLORS["warning"],
    "DEGRADED": COLORS["warning"],
    "FAULT": COLORS["error"],
    "RECOVERING": COLORS["warning"],
    "OFFLINE": COLORS["offline"],
}

# Vehicle Overview / dashboard-wide ECU catalog. Each id maps 1:1 to a future
# FreeRTOS task on the STM32 (EngineTask, BatteryTask, ...).
ECU_CATALOG = [
    {"id": "engine", "name": "Motor ECU", "task": "EngineTask"},
    {"id": "battery", "name": "Battery ECU", "task": "BatteryTask"},
    {"id": "brake", "name": "Brake ECU", "task": "BrakeTask"},
    {"id": "steering", "name": "Steering ECU", "task": "SteeringTask"},
    {"id": "climate", "name": "Climate ECU", "task": "ClimateTask"},
    {"id": "adas", "name": "ADAS ECU", "task": "ADAS_Task"},
]

FAULT_CATALOG = {
    "engine": {
        "fault_id": "MOTOR_OVERTEMP",
        "label": "Motor over-temperature",
        "severity": "CRITICAL",
        "telemetry": {"engine_temp": 118.0},
    },
    "battery": {
        "fault_id": "BATT_TEMP_HIGH",
        "label": "Battery over-temperature",
        "severity": "WARNING",
        "telemetry": {"battery_voltage": 11.4, "battery_soc": 41.0},
    },
    "brake": {
        "fault_id": "BRAKE_SENSOR_FAIL",
        "label": "Brake sensor failure",
        "severity": "CRITICAL",
        "telemetry": {"brake_status": "FAULT"},
    },
    "steering": {
        "fault_id": "STEERING_COMM_LOSS",
        "label": "Steering communication loss",
        "severity": "WARNING",
        "telemetry": {"steering_status": "FAULT"},
    },
    "climate": {
        "fault_id": "CLIMATE_SENSOR_DRIFT",
        "label": "Climate sensor drift",
        "severity": "INFO",
        "telemetry": {"cabin_temp": 31.5},
    },
    "adas": {
        "fault_id": "ADAS_SENSOR_BLOCKED",
        "label": "ADAS sensor blocked",
        "severity": "WARNING",
        "telemetry": {"adas_status": "FAULT"},
    },
    "communication": {
        "fault_id": "CAN_BUS_ERROR",
        "label": "CAN bus error",
        "severity": "CRITICAL",
        "telemetry": {},
    },
}

# DBC-style signal catalog — CAN_ID, message, signal(s), factor/offset/unit,
# sender/receiver. In-memory stand-in for a real .dbc file (see docs).
DBC_CATALOG = [
    {"can_id": "0x101", "message": "MotorStatus", "signal": "motor_rpm", "factor": 1, "offset": 0, "unit": "rpm", "sender": "Motor ECU", "receiver": "ADAS ECU"},
    {"can_id": "0x102", "message": "BatteryStatus", "signal": "battery_voltage", "factor": 0.01, "offset": 0, "unit": "V", "sender": "Battery ECU", "receiver": "Motor ECU"},
    {"can_id": "0x103", "message": "BrakeStatus", "signal": "brake_pressure", "factor": 1, "offset": 0, "unit": "bar", "sender": "Brake ECU", "receiver": "ADAS ECU"},
    {"can_id": "0x104", "message": "SteeringStatus", "signal": "steering_angle", "factor": 0.1, "offset": -900, "unit": "deg", "sender": "Steering ECU", "receiver": "ADAS ECU"},
    {"can_id": "0x105", "message": "ClimateStatus", "signal": "cabin_temp", "factor": 0.1, "offset": -40, "unit": "°C", "sender": "Climate ECU", "receiver": "Motor ECU"},
    {"can_id": "0x106", "message": "ADASStatus", "signal": "adas_state", "factor": 1, "offset": 0, "unit": "enum", "sender": "ADAS ECU", "receiver": "Motor ECU"},
]

# Sidebar: (section, [(display, icon, route), ...])
NAVIGATION = [
    ("VEHICLE", [
        ("Vehicle Overview", "\u25CE", "overview"),
        ("Live Telemetry", "\u2261", "telemetry"),
        ("Virtual ECUs", "\u25CB", "ecus"),
        ("Digital Twin", "\u25C8", "twin"),
        ("CAN / DBC Monitor", "\u2394", "can"),
    ]),
    ("SOFTWARE", [
        ("OTA Manager", "\u2191", "ota"),
        ("Diagnostics", "\u2691", "diagnostics"),
        ("Fault Injection", "\u26A1", "fault"),
        ("Autonomous Recovery", "\u21BB", "recovery"),
        ("System Logs", "\u2261", "logs"),
    ]),
    ("INTELLIGENCE", [
        ("ARI Assistant", "\u2726", "ari"),
        ("Voice Assistant", "\u25C9", "voice"),
    ]),
    ("DATA", [
        ("History", "\u2637", "history"),
        ("Settings", "\u2699", "settings"),
    ]),
]
