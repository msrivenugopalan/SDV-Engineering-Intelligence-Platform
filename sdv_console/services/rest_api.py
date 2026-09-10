"""REST layer (architecture doc §16) — sits between the outside world and
Central State via EngineeringPlatform, never touched directly by any view.
"""

from __future__ import annotations

from typing import Any

from flask import Flask, jsonify, request

from sdv_console.config import REST_HOST, REST_PORT


def create_app(platform: Any) -> Flask:
    app = Flask(__name__)

    @app.get("/state")
    def state():
        return jsonify(platform.snapshot())

    @app.get("/telemetry")
    def telemetry():
        return jsonify(platform.snapshot()["telemetry"])

    @app.get("/diagnostics")
    def diagnostics():
        return jsonify(platform.snapshot()["diagnostics"])

    @app.get("/ota")
    def ota():
        return jsonify(platform.snapshot()["ota"])

    @app.get("/history/events")
    def history_events():
        ecu = request.args.get("ecu")
        event_type = request.args.get("type")
        return jsonify(platform.history.query_events(ecu=ecu, event_type=event_type))

    @app.post("/fault/inject")
    def inject_fault():
        body = request.get_json(silent=True) or {}
        ecu_id = body.get("ecu")
        if not ecu_id:
            return jsonify({"ok": False, "error": "missing 'ecu'"}), 400
        return jsonify(platform.inject_fault(ecu_id))

    @app.post("/ota/start")
    def start_ota():
        body = request.get_json(silent=True) or {}
        return jsonify(platform.start_ota(body.get("target_ecu", "Battery ECU"), body.get("target_version", "v2.0.0")))

    @app.post("/hardware/ingest")
    def hardware_ingest():
        """STM32 (via ESP32 gateway) posts telemetry/ecu/can/event JSON here.
        A successful call is the only thing that flips the console's
        STM32/ESP32 indicators to CONNECTED — see adapters/hardware.py.
        """
        body = request.get_json(silent=True)
        if not isinstance(body, dict):
            return jsonify({"ok": False, "error": "expected a JSON object body"}), 400
        platform.hardware.ingest(body)
        return jsonify({"ok": True})

    return app


def run_rest_thread(platform: Any):
    import threading

    app = create_app(platform)

    def _run():
        app.run(host=REST_HOST, port=REST_PORT, debug=False, use_reloader=False)

    thread = threading.Thread(target=_run, daemon=True)
    thread.start()
    platform.state.set_service(rest=True)
    return thread
