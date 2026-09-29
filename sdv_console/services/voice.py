"""Voice Assistant — a system-aware conversational layer for the SDV console.

This service accepts free-form questions about the live console state and
answers with grounded information from Central State, rather than forcing the
user into a rigid command list.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from typing import Any

from sdv_console.config import ECU_CATALOG, FAULT_CATALOG
from sdv_console.core.vehicle_state import VehicleState
from sdv_console.services.ari import ARIService

ECU_ALIASES = {
    "battery": "battery",
    "battery ecu": "battery",
    "battery controller": "battery",
    "battery control unit": "battery",
    "motor": "engine",
    "motor ecu": "engine",
    "motor controller": "engine",
    "motor control unit": "engine",
    "engine": "engine",
    "engine ecu": "engine",
    "brake": "brake",
    "brake ecu": "brake",
    "steering": "steering",
    "steering ecu": "steering",
    "climate": "climate",
    "climate ecu": "climate",
    "adas": "adas",
    "adas ecu": "adas",
}

FAULT_TYPES = {
    "over_temperature": ("over temperature", "overtemp", "overheating", "too hot", "temperature"),
    "sensor_failure": ("sensor failure", "sensor fault", "sensor failed"),
    "communication_loss": ("communication loss", "comm loss", "lost communication"),
    "sensor_drift": ("sensor drift", "drifting sensor"),
    "sensor_blocked": ("sensor blocked", "blocked sensor"),
}

TELEMETRY_ALIASES = {
    "battery voltage": "battery_voltage",
    "battery soc": "battery_soc",
    "state of charge": "battery_soc",
    "battery current": "battery_current",
    "battery power": "battery_power",
    "vehicle speed": "vehicle_speed",
    "speed": "vehicle_speed",
    "motor temperature": "engine_temp",
    "engine temperature": "engine_temp",
    "cabin temperature": "cabin_temp",
    "cabin temp": "cabin_temp",
    "estimated range": "estimated_range",
}


class VoiceService:
    def __init__(
        self,
        state: VehicleState,
        ari: ARIService,
        inject_fault: Callable[[str], dict[str, Any]] | None = None,
        start_recovery: Callable[[str], dict[str, Any]] | None = None,
    ) -> None:
        self.state = state
        self.ari = ari
        self.inject_fault = inject_fault
        self.start_recovery = start_recovery

    def handle(self, utterance: str) -> str:
        text = (utterance or "").strip()
        if not text:
            return "Say a question or command about the vehicle system."

        query = self._normalize(text)
        if self._matches(query, ["aging", "prediction", "predictive", "thermal model"]):
            return self._fallback_response(query)
        command = self._interpret(query)
        intent = command["intent"]

        if intent == "inject_fault":
            return self._inject_fault(command["target"], command["entities"].get("fault_type"), query)
        if intent == "recover_ecu":
            return self._recover_ecu(command["target"])
        if intent == "start_diagnostics":
            return "Starting a diagnostics run is not currently implemented. I can report existing diagnostic records with 'show diagnostics' or 'show active faults'."
        if intent == "active_faults":
            return self._fault_summary()
        if intent == "can_status":
            return self._can_summary()
        if intent == "ota_status":
            return self._ota_summary()
        if intent == "vehicle_health":
            return self.ari.explain_current_state()
        if intent == "battery_status":
            return self._battery_summary()
        if intent == "ecu_status":
            if command["target"]:
                return self._ecu_summary(command["target"])
            return self._all_ecu_summary()
        if intent == "diagnostics_status":
            return self._diagnostic_summary()
        if intent == "clarify_temperature":
            return "Which temperature should I check: battery, motor, or cabin?"

        if self._matches(query, ["help", "what can you do", "commands", "capabilities"]):
            return self._help_text()

        if self._matches(query, ["hello", "hi", "hey", "good morning", "good afternoon"]):
            return "Hello — I can help with live vehicle health, ECU status, faults, CAN, OTA, diagnostics, and recent system events."

        if self._matches(query, ["vehicle health", "system health", "overall health", "system summary", "overall status", "vehicle status", "status summary"]):
            return self.ari.explain_current_state()

        if self._matches(query, ["fault", "faults", "error", "errors", "issue", "issues", "problem", "problems"]):
            return self._fault_summary()

        if self._matches(query, ["attest", "verify deployed", "validate deployed", "deployed ota version", "show deployed firmware", "what firmware is deployed"]):
            return self._ota_attestation_summary()

        if self._matches(query, ["implement ota", "how to implement ota", "ota update process", "how do i do ota", "how to do ota"]):
            return self._ota_implementation_summary()

        if self._matches(query, ["can bus", "can status", "dbc", "bus state", "bus status", "communication"]):
            return self._can_summary()

        if self._matches(query, ["ota", "firmware", "firmware update", "deployment", "update status"]):
            return self._ota_summary()

        if self._matches(query, ["diagnostic", "diagnostics", "dtc", "fault code", "fault codes"]):
            return self._diagnostic_summary()

        if self._matches(query, ["mode", "connection", "connected", "disconnected", "simulation", "hardware"]):
            return self._mode_summary()

        if self._matches(query, ["service", "services", "mqtt", "rest", "sqlite", "stm32", "esp32"]):
            return self._services_summary()

        if self._matches(query, ["history", "recent events", "logs", "event log", "recent log"]):
            return self._history_summary()

        if self._matches(query, ["uptime", "firmware version", "software version", "version"]):
            return self._version_summary()

        metric = self._find_metric(query)
        if metric is not None:
            return self._metric_summary(metric)

        ecu = self._find_ecu(query)
        if ecu is not None:
            return self._ecu_summary(ecu)

        if self._matches(query, ["telemetry", "live telemetry", "sensor", "readings"]):
            return self._telemetry_summary()

        return self._fallback_response(query)

    def _help_text(self) -> str:
        return (
            "Supported: show vehicle health, battery or ECU status, active faults, CAN status, OTA status, diagnostics, or recent events; "
            "inject a catalog-supported ECU fault; or recover a faulted ECU. A new diagnostics run is not implemented."
        )

    def _interpret(self, query: str) -> dict[str, Any]:
        ecu = self._find_ecu(query)
        target = ecu or self._unknown_ecu(query)
        result = {"intent": "question", "target": target, "entities": {}, "confidence": 0.55}

        if self._matches(query, ["recover", "recovery"]):
            result.update(intent="recover_ecu", confidence=0.96)
            return result

        if self._matches(query, ["inject", "simulate", "trigger", "create fault", "raise fault", "put", "into a fault"]):
            fault_type = self._find_fault_type(query)
            result.update(intent="inject_fault", entities={"fault_type": fault_type}, confidence=0.96 if target and fault_type else 0.65)
            return result

        if self._matches(query, ["start diagnostics", "run diagnostics", "run diagnostic", "start diagnostic"]):
            result.update(intent="start_diagnostics", confidence=0.96)
            return result
        if self._matches(query, ["show active fault", "active fault", "faults", "vehicle for faults", "dtc"]):
            result.update(intent="active_faults", confidence=0.94)
            return result
        if self._matches(query, ["can status", "can bus", "bus status", "communication status"]):
            result.update(intent="can_status", confidence=0.94)
            return result
        if self._matches(query, ["ota status", "firmware update status", "deployment status"]):
            result.update(intent="ota_status", confidence=0.94)
            return result
        if self._matches(query, ["show diagnostics", "diagnostic records", "diagnostic status", "fault codes"]):
            result.update(intent="diagnostics_status", confidence=0.92)
            return result
        if self._matches(query, ["vehicle health", "system health", "overall health", "vehicle status", "system summary"]):
            result.update(intent="vehicle_health", confidence=0.94)
            return result
        if target == "battery" and self._matches(query, ["status", "health", "how is", "how s", "information", "details", "doing", "about"]):
            result.update(intent="battery_status", target="battery", confidence=0.92)
            return result
        if target and self._matches(query, ["status", "health", "details", "information", "show", "about"]):
            result.update(intent="ecu_status", confidence=0.9)
            return result
        if self._matches(query, ["ecu status", "current ecu status", "all ecu"]):
            result.update(intent="ecu_status", target=None, confidence=0.88)
            return result
        if self._matches(query, ["temperature", "temp"]):
            result.update(intent="clarify_temperature", confidence=0.55)
        return result

    def _find_fault_type(self, query: str) -> str | None:
        for fault_type, phrases in FAULT_TYPES.items():
            if self._matches(query, list(phrases)):
                return fault_type
        return None

    def _fault_type_for_ecu(self, ecu_id: str) -> str | None:
        fault_id = FAULT_CATALOG.get(ecu_id, {}).get("fault_id", "").lower()
        if "temp" in fault_id:
            return "over_temperature"
        if "sensor_fail" in fault_id:
            return "sensor_failure"
        if "comm" in fault_id:
            return "communication_loss"
        if "drift" in fault_id:
            return "sensor_drift"
        if "blocked" in fault_id:
            return "sensor_blocked"
        return None

    def _unknown_ecu(self, query: str) -> str | None:
        match = re.search(r"\b([a-z]+)\s+(?:ecu|controller)\b", query)
        if not match:
            return None
        candidate = match.group(1)
        return None if candidate in ECU_ALIASES else candidate

    def _inject_fault(self, ecu_id: str | None, fault_type: str | None, query: str) -> str:
        if ecu_id and ecu_id not in {ecu["id"] for ecu in ECU_CATALOG}:
            return f"The {ecu_id} ECU is not supported by this console."
        if not ecu_id:
            return "Which ECU should I target? For example, Battery ECU or Motor ECU."
        if not fault_type:
            if self._has_unrecognized_fault_detail(query):
                return "That fault type is not in the implemented fault catalog."
            return "Which supported fault should I inject? For example, battery over-temperature or motor over-temperature."
        spec = FAULT_CATALOG.get(ecu_id)
        if not spec or self._fault_type_for_ecu(ecu_id) != fault_type:
            return f"That fault is not supported for the {self._ecu_label(ecu_id)}."
        if self.inject_fault is None:
            return "Fault injection is not available through the current application platform."
        try:
            result = self.inject_fault(ecu_id)
        except Exception as exc:
            return f"Unable to inject the fault because the fault service failed: {exc}"
        if not result.get("ok"):
            detail = result.get("detail") or result.get("error") or "unknown service error"
            return f"Unable to inject the fault: {detail}."
        return f"{spec['label']} fault injected successfully ({result.get('fault_id', spec['fault_id'])})."

    def _has_unrecognized_fault_detail(self, query: str) -> bool:
        remaining = query
        for alias in sorted(ECU_ALIASES, key=len, reverse=True):
            remaining = re.sub(rf"(?<![a-z0-9]){re.escape(alias)}(?![a-z0-9])", " ", remaining)
        ignored = {
            "inject", "simulate", "trigger", "create", "raise", "put", "set", "the", "a", "an",
            "into", "for", "of", "fault", "ecu", "controller", "control", "unit", "on", "to", "please",
        }
        return any(word not in ignored for word in remaining.split())

    def _recover_ecu(self, ecu_id: str | None) -> str:
        if ecu_id and ecu_id not in {ecu["id"] for ecu in ECU_CATALOG}:
            return f"The {ecu_id} ECU is not supported by this console."
        if not ecu_id:
            return "Which ECU should I recover? For example, Battery ECU or Motor ECU."
        if self.start_recovery is None:
            return "ECU recovery is not available through the current application platform."
        try:
            result = self.start_recovery(ecu_id)
        except Exception as exc:
            return f"Unable to start recovery because the recovery service failed: {exc}"
        if not result.get("ok"):
            detail = result.get("detail") or result.get("error") or "unknown service error"
            return f"Unable to recover the {self._ecu_label(ecu_id)}: {detail}."
        return f"Recovery started for the {self._ecu_label(ecu_id)}."

    def _ecu_label(self, ecu_id: str) -> str:
        return next((ecu["name"] for ecu in ECU_CATALOG if ecu["id"] == ecu_id), ecu_id)

    def _all_ecu_summary(self) -> str:
        ecus = self.state.snapshot()["ecus"]
        return "; ".join(
            f"{ecu['name']}: {ecu['status']}, health {ecu['health']}%"
            for ecu in ecus.values()
        ) + "."

    def _battery_summary(self) -> str:
        snap = self.state.snapshot()
        ecu = snap["ecus"].get("battery")
        if not ecu:
            return "Battery ECU state is not available."
        telemetry = snap["telemetry"]
        return (
            f"Battery ECU is {ecu['status'].lower()} with health at {ecu['health']}%. "
            f"State of charge is {telemetry.get('battery_soc', 'unavailable')}%, "
            f"voltage is {telemetry.get('battery_voltage', 'unavailable')} V."
        )

    def _find_ecu(self, query: str) -> str | None:
        for alias, ecu_id in ECU_ALIASES.items():
            if alias in query:
                return ecu_id
        return None

    def _find_metric(self, query: str) -> str | None:
        for phrase, key in TELEMETRY_ALIASES.items():
            if phrase in query:
                return key
        return None

    def _matches(self, query: str, phrases: list[str]) -> bool:
        for phrase in phrases:
            pattern = rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])"
            if re.search(pattern, query):
                return True
        return False

    def _normalize(self, text: str) -> str:
        normalized = re.sub(r"[^a-z0-9]+", " ", text.lower())
        normalized = re.sub(r"\b(?:please|um|uh|hey)", " ", normalized)
        return re.sub(r"\s+", " ", normalized).strip()

    def _metric_summary(self, metric: str) -> str:
        snap = self.state.snapshot()
        value = snap["telemetry"].get(metric)
        if value in (None, ""):
            return f"I couldn’t find a live value for {metric.replace('_', ' ')} right now."

        units = {
            "battery_voltage": "V",
            "battery_soc": "%",
            "battery_current": "A",
            "battery_power": "W",
            "vehicle_speed": "km/h",
            "engine_temp": "°C",
            "cabin_temp": "°C",
            "estimated_range": "km",
        }

        label = metric.replace("_", " ")
        unit = units.get(metric, "")
        if unit:
            return f"{label} is currently {value} {unit}."
        return f"{label} is currently {value}."

    def _fault_summary(self) -> str:
        snap = self.state.snapshot()
        faults = snap["active_faults"]
        if not faults:
            return "There are no active faults right now."

        names = ", ".join(f"{f['name']} ({f.get('fault_id')})" for f in faults)
        return f"There {'is' if len(faults) == 1 else 'are'} {len(faults)} active fault(s): {names}."

    def _can_summary(self) -> str:
        can = self.state.snapshot()["can"]
        return (
            f"CAN bus is {can['bus_state']}. "
            f"Recent rate is {can['messages_per_sec']} messages/sec, bus load is {can['bus_load_pct']}%, "
            f"and there have been {can['error_count']} error(s)."
        )

    def _ota_summary(self) -> str:
        ota = self.state.snapshot()["ota"]
        return (
            f"OTA status is {ota.get('status', 'IDLE')} at {ota.get('progress', 0)}%. "
            f"Current firmware is {ota.get('current_version', '—')}, target is {ota.get('target_version', '—')}, "
            f"and target ECU is {ota.get('target_ecu', '—')}."
        )

    def _ota_implementation_summary(self) -> str:
        return (
            "To implement an OTA update in this console, first open the OTA Manager, choose the target ECU and target firmware version, "
            "then start the deployment. The workflow is VALIDATING -> DOWNLOADING -> INSTALLING -> COMPLETED, and on completion the console "
            "updates the active firmware version, records the deployment in OTA history, and reflects the new version throughout the dashboard."
        )

    def _ota_attestation_summary(self) -> str:
        ota = self.state.snapshot()["ota"]
        status = ota.get("status", "IDLE")
        current = ota.get("current_version", "—")
        target = ota.get("target_version", "—")
        ecu = ota.get("target_ecu", "—")
        previous = ota.get("from_version", current)

        if status == "COMPLETED":
            return (
                f"OTA attestation is confirmed: {ecu} is now running {target} (previously {previous}). "
                f"Current firmware is {current}, and the OTA deployment completed successfully."
            )
        if status in {"VALIDATING", "DOWNLOADING", "INSTALLING"}:
            return (
                f"OTA attestation is still pending. The deployment is {status} at {ota.get('progress', 0)}% for {ecu}, "
                f"with current firmware {current} and target firmware {target}."
            )
        return (
            f"No completed OTA deployment is currently attested. The console shows current firmware {current}, target firmware {target}, "
            f"and OTA status {status}."
        )

    def _diagnostic_summary(self) -> str:
        diags = self.state.snapshot()["diagnostics"]
        active = [d for d in diags if d["status"] == "ACTIVE"]
        if not active:
            return "Diagnostics currently show no active DTCs."

        details = ", ".join(f"{d['fault_id']} on {d['ecu']}" for d in active)
        return f"There are {len(active)} active diagnostic record(s): {details}."

    def _mode_summary(self) -> str:
        snap = self.state.snapshot()
        return f"System mode is {snap['mode']} and connection label is {snap['connection_label']}."

    def _services_summary(self) -> str:
        snap = self.state.snapshot()
        services = snap.get("services", {})
        parts = []
        for name, enabled in services.items():
            parts.append(f"{name.upper()}={str(enabled).upper()}")
        return f"Service availability: {', '.join(parts)}."

    def _history_summary(self) -> str:
        snap = self.state.snapshot()
        events = snap.get("recent_events", [])[:5]
        if not events:
            return "There are no recent events in the system log."

        pieces = []
        for event in events:
            ts = (event.get("timestamp") or "")[11:19]
            pieces.append(f"{ts} {event.get('event_type', 'EVENT')}")
        return "Recent system events: " + "; ".join(pieces) + "."

    def _version_summary(self) -> str:
        snap = self.state.snapshot()
        return f"Current console firmware is {snap['firmware']} and system uptime started at {snap['uptime_started'][11:19]}."

    def _ecu_summary(self, ecu_id: str) -> str:
        ecu = self.state.snapshot()["ecus"].get(ecu_id)
        if not ecu:
            return f"I couldn’t find ECU information for {ecu_id}."

        return (
            f"{ecu['name']} is in {ecu['status']} state with health at {ecu['health']}%. "
            f"Firmware is {ecu['firmware']} and the last event was {ecu['last_event']}."
        )

    def _telemetry_summary(self) -> str:
        snap = self.state.snapshot()
        tel = snap["telemetry"]
        return (
            f"Live telemetry shows vehicle speed {tel.get('vehicle_speed', '—')} km/h, "
            f"battery voltage {tel.get('battery_voltage', '—')} V, battery SoC {tel.get('battery_soc', '—')}%, "
            f"engine temperature {tel.get('engine_temp', '—')} °C, and cabin temperature {tel.get('cabin_temp', '—')} °C."
        )

    def _system_summary(self) -> str:
        snap = self.state.snapshot()
        return (
            f"Overall vehicle health is {snap['overall_health']}. "
            f"System mode is {snap['mode']} with {snap['connection_label']}. "
            f"CAN bus is {snap['can']['bus_state']} and OTA is {snap['ota'].get('status', 'IDLE')} at {snap['ota'].get('progress', 0)}%."
        )

    def _fallback_response(self, query: str) -> str:
        if self._matches(query, ["aging", "prediction", "predictive", "thermal model"]):
            return "I recognize that as an SDV engineering capability, but battery aging prediction is not currently implemented in this console."
        return (
            "That command is outside the SDV Engineering Console capabilities. Supported examples: show vehicle health, battery status, "
            "active faults, CAN status, OTA status, diagnostics, recent events, inject a supported fault, or recover a faulted ECU."
        )
