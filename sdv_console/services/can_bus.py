"""CAN frame helper — packs simulated bytes using the project DBC factors."""

from __future__ import annotations

from sdv_console.core.events import utc_now_iso
from sdv_console.core.models import CANFrame
from sdv_console.services.dbc import message_by_ecu


def encode_payload(ecu_id: str, telemetry: dict, health: int, fault: bool) -> str:
    """8-byte hex string. Encoding matches firmware/PROTOCOL.md."""
    data = [0] * 8
    if ecu_id == "battery":
        voltage_raw = int(float(telemetry.get("battery_voltage", 0)) / 0.01)
        current_raw = int((float(telemetry.get("battery_current", 0)) + 100) / 0.01)
        data[0] = voltage_raw & 0xFF
        data[1] = (voltage_raw >> 8) & 0xFF
        data[2] = current_raw & 0xFF
        data[3] = (current_raw >> 8) & 0xFF
        data[4] = health & 0xFF
        data[5] = 1 if fault else 0
    elif ecu_id == "engine":
        temp_raw = int(float(telemetry.get("engine_temp", 0)) / 0.1)
        data[0] = temp_raw & 0xFF
        data[1] = (temp_raw >> 8) & 0xFF
        data[2] = health & 0xFF
        data[3] = 1 if fault else 0
    elif ecu_id == "brake":
        data[0] = 1 if telemetry.get("brake_status") == "APPLIED" else 0
        if telemetry.get("brake_status") == "FAULT":
            data[0] = 0xFF
        data[1] = health & 0xFF
        data[2] = 1 if fault else 0
    elif ecu_id == "steering":
        data[2] = health & 0xFF
        data[3] = 1 if fault else 0
    elif ecu_id == "climate":
        temp_raw = int((float(telemetry.get("cabin_temp", 0)) + 40) / 0.1)
        data[0] = temp_raw & 0xFF
        data[1] = (temp_raw >> 8) & 0xFF
        data[2] = health & 0xFF
        data[3] = 1 if fault else 0
    elif ecu_id == "adas":
        data[0] = 1 if telemetry.get("adas_status") == "ACTIVE" else 0
        if telemetry.get("adas_status") == "DEGRADED":
            data[0] = 2
        data[1] = health & 0xFF
        data[2] = 1 if fault else 0
    return " ".join(f"{b:02X}" for b in data)


def make_frame(ecu_id: str, ecu_name: str, telemetry: dict, health: int, fault: bool) -> CANFrame:
    meta = message_by_ecu(ecu_id)
    can_id = f"0x{meta['id']:03X}" if meta else "0x000"
    name = meta["name"] if meta else "Unknown"
    status = "ERROR" if fault else "OK"
    return CANFrame(
        timestamp=utc_now_iso(),
        can_id=can_id,
        ecu=ecu_name,
        message=name,
        data=encode_payload(ecu_id, telemetry, health, fault),
        direction="RX",
        status=status,
    )
