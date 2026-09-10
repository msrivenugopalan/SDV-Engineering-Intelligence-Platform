"""Voice Assistant — a system-aware conversational layer for the SDV console.

This service accepts free-form questions about the live console state and
answers with grounded information from Central State, rather than forcing the
user into a rigid command list.
"""

from __future__ import annotations

import re

from sdv_console.core.vehicle_state import VehicleState
from sdv_console.services.ari import ARIService

ECU_ALIASES = {
    "battery": "battery",
    "motor": "engine",
    "engine": "engine",
    "brake": "brake",
    "steering": "steering",
    "climate": "climate",
    "adas": "adas",
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
    def __init__(self, state: VehicleState, ari: ARIService) -> None:
        self.state = state
        self.ari = ari

    def handle(self, utterance: str) -> str:
        text = (utterance or "").strip()
        if not text:
            return "Say a question or command about the vehicle system."

        query = self._normalize(text)

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
            "I can answer questions about live vehicle health, ECU status, active faults, CAN bus, OTA progress, diagnostics, "
            "recent events, firmware versions, and current system services. Try asking for battery voltage, engine temperature, "
            "details for a specific ECU, or a general system summary."
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
        return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()

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
        if "what" in query or "why" in query or "how" in query:
            return (
                f"I can answer this using the live system state. Right now the console reports: {self._system_summary()}. "
                "Ask me about a specific ECU, telemetry value, fault, CAN bus, OTA update, diagnostics, or recent events."
            )

        return (
            f"I’m ready to help with the live SDV system. Current status: {self._system_summary()} "
            "You can ask about battery, engine, brake, steering, climate, ADAS, CAN, OTA, diagnostics, or recent events."
        )
