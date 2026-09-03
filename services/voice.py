"""Allow-list voice/command parser. Speech never executes arbitrary code."""

from __future__ import annotations

import re
from typing import Any

ECU_ALIASES = {
    "engine": "engine",
    "battery": "battery",
    "brake": "brake",
    "brakes": "brake",
    "steering": "steering",
    "climate": "climate",
    "cabin": "climate",
    "adas": "adas",
    "communication": "communication",
    "comms": "communication",
    "gateway": "communication",
}

DESTRUCTIVE = {"inject_fault", "start_ota"}


def parse_command(utterance: str) -> dict[str, Any]:
    text = (utterance or "").strip().lower()
    text = re.sub(r"[^a-z0-9\s.]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()

    if text in {"confirm", "yes", "proceed", "do it", "confirmed"}:
        return {"ok": True, "intent": "confirm", "destructive": False}
    if text in {"cancel", "no", "abort", "stop"}:
        return {"ok": True, "intent": "cancel", "destructive": False}

    if "can" in text and any(w in text for w in ("show", "traffic", "monitor", "messages")):
        return {"ok": True, "intent": "show_page", "page": "CAN Monitor", "destructive": False}

    if "ota" in text and any(w in text for w in ("start", "deploy", "begin", "run")):
        return {
            "ok": True,
            "intent": "start_ota",
            "target_ecu": "Battery ECU",
            "target_version": "v1.1",
            "destructive": True,
            "confirm_prompt": "OTA deployment to Battery ECU (v1.1) requested. Confirm?",
        }

    if "inject" in text or (
        "fault" in text and any(w in text for w in ("inject", "trigger", "simulate"))
    ):
        ecu = _find_ecu(text)
        if not ecu:
            return {"ok": False, "error": "unknown_ecu", "detail": "Name an ECU to inject a fault."}
        return {
            "ok": True,
            "intent": "inject_fault",
            "ecu": ecu,
            "destructive": True,
            "confirm_prompt": f"{ecu} fault injection requested. Confirm?",
        }

    if "recover" in text or "start recovery" in text:
        return {"ok": True, "intent": "start_recovery", "destructive": False}

    if "active fault" in text or "show fault" in text or "what fault" in text:
        return {"ok": True, "intent": "show_faults", "destructive": False}

    if "battery voltage" in text or "current battery" in text:
        return {"ok": True, "intent": "query_battery_voltage", "destructive": False}

    if "happened" in text or "what happened" in text:
        ecu = _find_ecu(text)
        return {"ok": True, "intent": "query_ecu", "ecu": ecu or "brake", "destructive": False}

    if "battery status" in text or "battery" in text and "show" in text:
        return {"ok": True, "intent": "query_ecu", "ecu": "battery", "destructive": False}

    if "vehicle status" in text or "show vehicle" in text or "vehicle health" in text:
        return {"ok": True, "intent": "show_vehicle_status", "destructive": False}

    if "digital twin" in text:
        return {"ok": True, "intent": "show_page", "page": "Digital Twin", "destructive": False}

    if "telemetry" in text:
        return {"ok": True, "intent": "show_page", "page": "Live Telemetry", "destructive": False}

    return {
        "ok": False,
        "error": "unsupported_command",
        "detail": "That phrase is not in the engineering command list.",
    }


def _find_ecu(text: str) -> str | None:
    for alias, ecu_id in ECU_ALIASES.items():
        if alias in text:
            return ecu_id
    return None
