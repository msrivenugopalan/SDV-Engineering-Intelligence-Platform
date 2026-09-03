"""Lightweight project DBC — message/signal dictionary, not a .dbc file parser."""

from __future__ import annotations

from sdv_console.config import ECU_CATALOG

# Signals match what STM32 CAN TX should eventually pack (little-endian, integer).
DBC_MESSAGES = [
    {
        "id": 0x101,
        "id_hex": "0x101",
        "name": "BatteryStatus",
        "sender": "Battery ECU",
        "dlc": 8,
        "signals": [
            {"name": "Voltage", "start_bit": 0, "length": 16, "factor": 0.01, "offset": 0, "unit": "V"},
            {"name": "Current", "start_bit": 16, "length": 16, "factor": 0.01, "offset": -100, "unit": "A"},
            {"name": "Health", "start_bit": 32, "length": 8, "factor": 1, "offset": 0, "unit": "%"},
            {"name": "FaultFlag", "start_bit": 40, "length": 8, "factor": 1, "offset": 0, "unit": ""},
        ],
    },
    {
        "id": 0x102,
        "id_hex": "0x102",
        "name": "EngineStatus",
        "sender": "Engine ECU",
        "dlc": 8,
        "signals": [
            {"name": "Temperature", "start_bit": 0, "length": 16, "factor": 0.1, "offset": 0, "unit": "C"},
            {"name": "Health", "start_bit": 16, "length": 8, "factor": 1, "offset": 0, "unit": "%"},
            {"name": "FaultFlag", "start_bit": 24, "length": 8, "factor": 1, "offset": 0, "unit": ""},
        ],
    },
    {
        "id": 0x103,
        "id_hex": "0x103",
        "name": "BrakeStatus",
        "sender": "Brake ECU",
        "dlc": 8,
        "signals": [
            {"name": "Applied", "start_bit": 0, "length": 8, "factor": 1, "offset": 0, "unit": ""},
            {"name": "Health", "start_bit": 8, "length": 8, "factor": 1, "offset": 0, "unit": "%"},
            {"name": "FaultFlag", "start_bit": 16, "length": 8, "factor": 1, "offset": 0, "unit": ""},
        ],
    },
    {
        "id": 0x104,
        "id_hex": "0x104",
        "name": "SteeringStatus",
        "sender": "Steering ECU",
        "dlc": 8,
        "signals": [
            {"name": "Angle", "start_bit": 0, "length": 16, "factor": 0.1, "offset": -780, "unit": "deg"},
            {"name": "Health", "start_bit": 16, "length": 8, "factor": 1, "offset": 0, "unit": "%"},
            {"name": "FaultFlag", "start_bit": 24, "length": 8, "factor": 1, "offset": 0, "unit": ""},
        ],
    },
    {
        "id": 0x105,
        "id_hex": "0x105",
        "name": "ClimateStatus",
        "sender": "Climate ECU",
        "dlc": 8,
        "signals": [
            {"name": "CabinTemp", "start_bit": 0, "length": 16, "factor": 0.1, "offset": -40, "unit": "C"},
            {"name": "Health", "start_bit": 16, "length": 8, "factor": 1, "offset": 0, "unit": "%"},
            {"name": "FaultFlag", "start_bit": 24, "length": 8, "factor": 1, "offset": 0, "unit": ""},
        ],
    },
    {
        "id": 0x106,
        "id_hex": "0x106",
        "name": "ADASStatus",
        "sender": "ADAS ECU",
        "dlc": 8,
        "signals": [
            {"name": "FeatureState", "start_bit": 0, "length": 8, "factor": 1, "offset": 0, "unit": ""},
            {"name": "Health", "start_bit": 8, "length": 8, "factor": 1, "offset": 0, "unit": "%"},
            {"name": "FaultFlag", "start_bit": 16, "length": 8, "factor": 1, "offset": 0, "unit": ""},
        ],
    },
]


def messages() -> list[dict]:
    return DBC_MESSAGES


def message_by_ecu(ecu_id: str) -> dict | None:
    catalog = {item["id"]: item for item in ECU_CATALOG}
    meta = catalog.get(ecu_id)
    if not meta:
        return None
    for message in DBC_MESSAGES:
        if message["id"] == meta["can_id"]:
            return message
    return None
