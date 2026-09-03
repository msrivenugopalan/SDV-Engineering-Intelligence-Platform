"""Application configuration — theme, ECU catalog, thresholds, and ports.

Keep vehicle/network constants here so firmware (STM32 CAN IDs) and the
console stay aligned. Do not put secrets in this file.
"""

from pathlib import Path

APP_TITLE = "SDV Engineering Console"
APP_VERSION = "1.0"
VEHICLE_NAME = "SDV Engineering Prototype"

WINDOW_WIDTH = 1400
WINDOW_HEIGHT = 860
MIN_WINDOW_WIDTH = 1100
MIN_WINDOW_HEIGHT = 700

SIDEBAR_WIDTH = 236
HEADER_HEIGHT = 72
STATUS_BAR_HEIGHT = 40

# Local engineering APIs (loopback only — not a public cloud).
REST_HOST = "127.0.0.1"
REST_PORT = 5050

# MQTT is optional. Leave host empty until a broker exists.
MQTT_HOST = ""
MQTT_PORT = 1883
MQTT_TOPIC_TELEMETRY = "sdv/esp32/telemetry"
MQTT_TOPIC_EVENTS = "sdv/esp32/events"
MQTT_TOPIC_COMMANDS = "sdv/console/commands"

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"
SQLITE_PATH = DATA_DIR / "sdv_history.sqlite"

TICK_MS = 250
TELEMETRY_HISTORY_POINTS = 80
CAN_BUFFER_SIZE = 200
EVENT_BUFFER_SIZE = 400

COLORS = {
    "bg_primary": "#0f1117",
    "bg_secondary": "#161b22",
    "bg_sidebar": "#12151c",
    "bg_header": "#1a1f2e",
    "bg_card": "#1c2128",
    "accent": "#3b82f6",
    "accent_muted": "#2563eb",
    "accent_blueprint": "#58a6ff",
    "text_primary": "#f0f6fc",
    "text_secondary": "#8b949e",
    "text_muted": "#6e7681",
    "border": "#30363d",
    "success": "#3fb950",
    "warning": "#d29922",
    "error": "#f85149",
    "recovering": "#e09b13",
    "offline": "#484f58",
}

HEADER_INFO = {
    "vehicle": VEHICLE_NAME,
    "firmware_version": "v1.0",
}

NAVIGATION_ITEMS = [
    "Vehicle Overview",
    "Virtual ECUs",
    "Digital Twin",
    "Live Telemetry",
    "CAN Monitor",
    "DBC / Vehicle Network",
    "Fault Injection",
    "Diagnostics",
    "Autonomous Recovery",
    "OTA Manager",
    "Voice Assistant",
    "Event / Fault History",
    "System Logs",
    "Settings",
]

# Health colors used by Digital Twin and ECU cards.
STATUS_COLORS = {
    "HEALTHY": COLORS["success"],
    "WARNING": COLORS["warning"],
    "FAULT": COLORS["error"],
    "RECOVERING": COLORS["recovering"],
    "OFFLINE": COLORS["offline"],
}

# Virtual ECUs — each maps to a FreeRTOS task on STM32 Nucleo-F446RE.
ECU_CATALOG = [
    {
        "id": "engine",
        "name": "Engine ECU",
        "task_name": "EngineTask()",
        "responsibility": "Engine temperature and operating mode for the prototype powertrain model.",
        "can_id": 0x102,
        "message_name": "EngineStatus",
    },
    {
        "id": "battery",
        "name": "Battery ECU",
        "task_name": "BatteryTask()",
        "responsibility": "Pack voltage, current, and power supervision.",
        "can_id": 0x101,
        "message_name": "BatteryStatus",
    },
    {
        "id": "brake",
        "name": "Brake ECU",
        "task_name": "BrakeTask()",
        "responsibility": "Brake apply status and hydraulic-model integrity.",
        "can_id": 0x103,
        "message_name": "BrakeStatus",
    },
    {
        "id": "steering",
        "name": "Steering ECU",
        "task_name": "SteeringTask()",
        "responsibility": "Steering angle validity and assist state.",
        "can_id": 0x104,
        "message_name": "SteeringStatus",
    },
    {
        "id": "climate",
        "name": "Climate ECU",
        "task_name": "ClimateTask()",
        "responsibility": "Cabin temperature regulation.",
        "can_id": 0x105,
        "message_name": "ClimateStatus",
    },
    {
        "id": "adas",
        "name": "ADAS ECU",
        "task_name": "ADAS_Task()",
        "responsibility": "Prototype ADAS feature enable and object-status flags.",
        "can_id": 0x106,
        "message_name": "ADASStatus",
    },
]

SYSTEM_TASKS = [
    {
        "id": "diagnostics",
        "name": "Diagnostics",
        "task_name": "DiagnosticsTask()",
        "responsibility": "Evaluates thresholds and publishes diagnostic records.",
    },
    {
        "id": "fault_manager",
        "name": "Fault Manager",
        "task_name": "FaultManagerTask()",
        "responsibility": "Owns active fault list and severity.",
    },
    {
        "id": "recovery",
        "name": "Recovery Manager",
        "task_name": "RecoveryTask()",
        "responsibility": "Runs Autonomous Recovery Intelligence (ARI) policies.",
    },
    {
        "id": "communication",
        "name": "Communication Manager",
        "task_name": "CommunicationTask()",
        "responsibility": "UART to ESP32 gateway and CAN TX/RX coordination.",
    },
]

# Engineering fault catalog (software injection + future STM32 fault IDs).
FAULT_CATALOG = {
    "engine": {
        "fault_id": "ENGINE_OVERTEMP",
        "label": "Engine fault",
        "severity": "HIGH",
        "description": "Engine temperature exceeded the configured operating limit.",
        "possible_cause": "Sustained high load or cooling-path fault in the engine model.",
        "telemetry": {"engine_temp": 118.0},
    },
    "battery": {
        "fault_id": "BATTERY_LOW_VOLTAGE",
        "label": "Battery fault",
        "severity": "HIGH",
        "description": "Battery voltage below the configured threshold.",
        "possible_cause": "Low battery condition or voltage-sense path error.",
        "telemetry": {"battery_voltage": 10.2, "battery_current": 18.5},
    },
    "brake": {
        "fault_id": "BRAKE_CIRCUIT_FAULT",
        "label": "Brake fault",
        "severity": "CRITICAL",
        "description": "Brake status invalid or circuit integrity check failed.",
        "possible_cause": "Sensor disagreement or actuator-loop fault in the brake model.",
        "telemetry": {"brake_status": "FAULT"},
    },
    "steering": {
        "fault_id": "STEERING_ANGLE_INVALID",
        "label": "Steering fault",
        "severity": "HIGH",
        "description": "Steering angle report is out of range or stale.",
        "possible_cause": "Angle sensor timeout or assist-task stall.",
        "telemetry": {"steering_status": "INVALID"},
    },
    "climate": {
        "fault_id": "CLIMATE_SENSOR_FAULT",
        "label": "Climate fault",
        "severity": "MEDIUM",
        "description": "Cabin temperature reading implausible.",
        "possible_cause": "Cabin sensor open/short in the climate model.",
        "telemetry": {"cabin_temp": -40.0},
    },
    "adas": {
        "fault_id": "ADAS_FEATURE_DEGRADED",
        "label": "ADAS fault",
        "severity": "MEDIUM",
        "description": "ADAS feature set entered a degraded state.",
        "possible_cause": "Internal ADAS task exception or input timeout.",
        "telemetry": {"adas_status": "DEGRADED"},
    },
    "communication": {
        "fault_id": "COMM_GATEWAY_FAULT",
        "label": "Communication fault",
        "severity": "HIGH",
        "description": "Gateway/CAN communication integrity fault.",
        "possible_cause": "UART framing error or CAN error-passive condition.",
        "telemetry": {},
    },
}

# Nominal simulated telemetry (not physical sensors until hardware mode).
NOMINAL_TELEMETRY = {
    "engine_temp": 86.0,
    "battery_voltage": 12.4,
    "battery_current": 4.2,
    "battery_power": 52.08,
    "brake_status": "RELEASED",
    "steering_status": "CENTERED",
    "cabin_temp": 22.5,
    "adas_status": "STANDBY",
    "vehicle_state": "RUNNING",
}

DIAGNOSTIC_THRESHOLDS = {
    "battery_voltage_low": 11.2,
    "battery_voltage_critical": 10.5,
    "engine_temp_high": 105.0,
    "engine_temp_critical": 115.0,
}

# Kept for any leftover overview helpers; live values come from VehicleState.
VEHICLE_STATUS_CONNECTED = [
    {"label": "Vehicle Status", "value": "Running"},
    {"label": "Power", "value": "ON"},
    {"label": "Gateway", "value": "Simulation"},
    {"label": "Cloud", "value": "Local"},
    {"label": "FreeRTOS", "value": "Simulated"},
]

VEHICLE_STATUS_DISCONNECTED = [
    {"label": "Vehicle Status", "value": "Idle"},
    {"label": "Power", "value": "OFF"},
    {"label": "Gateway", "value": "Disconnected"},
    {"label": "Cloud", "value": "Disconnected"},
    {"label": "FreeRTOS", "value": "Stopped"},
]

QUICK_STATS_CONNECTED = []
QUICK_STATS_DISCONNECTED = []

DIGITAL_TWIN_COMPONENTS = ["Engine", "Battery", "Brake", "Steering", "Climate", "ADAS"]

SYSTEM_STATUS_CONNECTED = []
SYSTEM_STATUS_DISCONNECTED = []
