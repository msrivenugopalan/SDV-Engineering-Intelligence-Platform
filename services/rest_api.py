"""Local REST API for commands and queries. Live UI still uses the event bus."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from flask import Flask, jsonify, request

from sdv_console.config import REST_HOST, REST_PORT
from sdv_console.services.dbc import messages as dbc_messages

if TYPE_CHECKING:
    from sdv_console.platform import EngineeringPlatform


def create_app(platform: EngineeringPlatform) -> Flask:
    app = Flask("sdv_engineering_api")
    app.config["JSON_SORT_KEYS"] = False

    @app.get("/vehicle/status")
    def vehicle_status():
        snap = platform.snapshot()
        return jsonify(
            {
                "vehicle": snap["vehicle_name"],
                "mode": snap["mode"],
                "connection": snap["connection_label"],
                "firmware": snap["firmware"],
                "overall_health": snap["overall_health"],
                "telemetry": snap["telemetry"],
            }
        )

    @app.get("/ecus")
    def ecus():
        return jsonify(platform.snapshot()["ecus"])

    @app.get("/telemetry")
    def telemetry():
        snap = platform.snapshot()
        return jsonify({"current": snap["telemetry"], "history": snap["telemetry_history"]})

    @app.get("/history")
    def history():
        return jsonify(
            platform.history.query_events(
                ecu=request.args.get("ecu"),
                event_type=request.args.get("event_type"),
                severity=request.args.get("severity"),
            )
        )

    @app.get("/faults")
    def faults():
        return jsonify(platform.snapshot()["diagnostics"])

    @app.get("/can/messages")
    def can_messages():
        snap = platform.snapshot()
        return jsonify({"bus": snap["can"], "frames": snap["can_frames"]})

    @app.get("/dbc")
    def dbc():
        return jsonify(dbc_messages())

    @app.post("/fault/inject")
    def fault_inject():
        body = request.get_json(silent=True) or {}
        ecu = body.get("ecu") or request.args.get("ecu")
        if not ecu:
            return jsonify({"ok": False, "error": "ecu required"}), 400
        return jsonify(platform.inject_fault(str(ecu)))

    @app.post("/recovery/start")
    def recovery_start():
        body = request.get_json(silent=True) or {}
        return jsonify(platform.start_recovery(body.get("ecu")))

    @app.post("/ota/start")
    def ota_start():
        body = request.get_json(silent=True) or {}
        return jsonify(
            platform.start_ota(
                body.get("target_ecu", "Battery ECU"),
                body.get("target_version", "v1.1"),
            )
        )

    @app.get("/ota/status")
    def ota_status():
        return jsonify(platform.snapshot()["ota"])

    @app.post("/voice/command")
    def voice_command():
        body = request.get_json(silent=True) or {}
        text = body.get("text") or body.get("utterance") or ""
        confirmed = bool(body.get("confirm"))
        return jsonify(platform.handle_voice(str(text), confirmed=confirmed))

    @app.get("/ari")
    def ari():
        return jsonify(platform.snapshot()["ari"])

    return app


def run_rest_thread(platform: EngineeringPlatform) -> Any:
    import threading

    app = create_app(platform)

    def _run() -> None:
        app.run(host=REST_HOST, port=REST_PORT, debug=False, use_reloader=False, threaded=True)

    thread = threading.Thread(target=_run, name="sdv-rest", daemon=True)
    thread.start()
    platform.state.set_service_flags(rest=True)
    return thread
