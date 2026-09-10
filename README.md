# SDV Engineering Console

A ground-up rebuild of the Intelligent Software-Defined Vehicle Engineering
Platform, built directly from the architecture spec: **one Central State,
one Event Bus, thirteen views that all read the same snapshot** — nothing
computes its own parallel copy of vehicle data.

## Run it

```bash
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

Opens the console window, starts the simulation, and starts a local REST
API on `http://127.0.0.1:5050`.

## Architecture — how this maps to the spec

```
app.py                 Tk root: header + sidebar + content + status bar,
                        drives the 250ms tick, starts the REST thread.

sdv_console/
  config.py             Every constant: colors, nav, ECU catalog, fault
                         catalog, DBC signal catalog, ports, tick rate.

  core/
    vehicle_state.py     CENTRAL STATE — the single source of truth (§3).
                         Every mutation is lock-guarded and publishes an
                         event. snapshot() is dirty-flag cached: cheap to
                         call repeatedly within one tick, always fresh
                         after any real change.
    event_bus.py          The "Events" node in the diagram (§3) — pub/sub.
    models.py              ECUState, CANFrame, DiagnosticRecord, OTASession,
                          RecoverySession, VehicleEvent dataclasses.

  adapters/               "Simulation vs Hardware Mode" (§18) — both
                         implement the same VehicleSource interface and
                         write into Central State through the identical
                         calls, so switching modes is a flag flip, not a
                         rewrite.
    simulation.py          Generates telemetry noise, CAN traffic for all
                         6 ECUs, fault injection, and a timed recovery
                         state machine.
    hardware.py             STM32/ESP32 ingestion point. `ingest()` is the
                         ONE place real hardware JSON enters the app —
                         REST's POST /hardware/ingest and MQTT both call it.
                         Marks the link connected on first message, and
                         auto-disconnects after 5s of silence.

  services/
    ota.py                  OTA state machine: VALIDATING → DOWNLOADING →
                          INSTALLING → COMPLETED (§13), ~5.4s animated.
    ari.py                   ARI — rule-based insight generator (§14).
                          Every sentence traces to a real state field;
                          it never invents a vehicle condition.
    voice.py                 Typed command handler (§15) — same handler a
                          real speech recognizer would feed later.
    history.py                SQLite persistence (§17), one persistent
                          WAL-mode connection, subscribed to every event.
    mqtt_bridge.py             Optional — idle if paho-mqtt isn't installed
                          or MQTT_HOST isn't set in config.py.
    rest_api.py                Flask layer (§16): GET /state, /telemetry,
                          /diagnostics, /ota, /history/events; POST
                          /fault/inject, /ota/start, /hardware/ingest.

  platform.py              EngineeringPlatform — the "APPLICATION / API
                         LAYER" box (§3). Every view/button calls a method
                         here; nothing reaches into VehicleState, an
                         adapter, or a service directly.

  components/              Header, sidebar, status bar, content switcher,
                         reusable widgets (PanelCard, MetricTile, ECUTile,
                         SparklineCanvas), and the Digital Twin canvas.

  views/                  One file per sidebar page — 14 in total, listed
                         below. Every refresh() reads platform.snapshot()
                         and nothing else.
```

## Why it stays smooth navigating between pages

- All 14 views are built once at startup and swapped with `tkraise()` —
  never rebuilt on navigation.
- `snapshot()` is cached per state-version, so the several components that
  call it within one 250ms tick (header, status bar, the active view) pay
  the deep-copy cost once, not repeatedly.
- The Digital Twin draws its static geometry once per canvas size and only
  `itemconfig`s the handful of items that actually change (ECU node color
  and status text) — not a full delete+redraw every tick.
- Text-heavy views (CAN Monitor, Diagnostics, History) compare a small
  "stamp" of the data that actually drives their content and skip the
  textbox rebuild when nothing changed.
- Only the *currently visible* view's `refresh()` runs each tick — the
  other 13 do nothing until you navigate to them.

## Where the numbers come from before STM32 is connected

`adapters/simulation.py` generates believable telemetry (`random.Random(42)`,
deterministic) and CAN traffic for all 6 ECUs, every 250ms tick — through
the exact same `state.update_telemetry()` / `state.add_can_frame()` calls
real hardware uses. Nothing about the UI changes when you switch sources;
only where the numbers come from changes.

## Connecting the real STM32

1. Your ESP32 gateway posts STM32 telemetry/ECU/CAN/event JSON to
   `POST http://127.0.0.1:5050/hardware/ingest` (or publishes the same
   JSON over MQTT if `MQTT_HOST` is configured and `paho-mqtt` is
   installed). Shapes are documented in `adapters/hardware.py`:
   ```json
   {"type": "telemetry", "engine_temp": 91.4, "battery_voltage": 12.7}
   {"type": "ecu", "ecu": "battery", "status": "FAULT", "health": 40}
   {"type": "can", "can_id": "0x102", "message": "BatteryStatus", "ecu": "battery", "direction": "RX", "status": "OK", "data": "V=12.6"}
   {"type": "event", "event_type": "FAULT_DETECTED", "ecu": "battery", "severity": "WARNING"}
   ```
2. The first successful call flips `services.stm32` / `services.esp32` to
   `true` — visible in the header, status bar, and Settings page.
3. A 5-second silence timeout auto-flips it back to disconnected, so the
   indicator stays honest instead of latching "connected" forever.
4. Once connected, Settings → "Try HARDWARE MODE" succeeds. Fault
   injection / recovery / OTA over hardware currently return an honest
   `hardware_read_only` response — the firmware-side command channel is
   the next piece to build, and `adapters/hardware.py` is exactly where
   that would be wired in.

## Every page in the sidebar

**VEHICLE** — Vehicle Overview (system summary only) · Live Telemetry
(gridded chart, metric selector) · Virtual ECUs (FreeRTOS task map) ·
Digital Twin (full-size) · CAN / DBC Monitor (live frames + signal catalog)

**SOFTWARE** — OTA Manager (with a completion banner) · Diagnostics (DTC
list) · Fault Injection · Autonomous Recovery · System Logs (live event
stream)

**INTELLIGENCE** — ARI Assistant (rule-based insight feed) · Voice
Assistant (typed command handler)

**DATA** — History (persisted, filterable SQLite query) · Settings (mode
switch + service status)

## What's genuinely a stub, said plainly

- Fault injection / recovery / OTA *initiated from the console while in
  HARDWARE mode* return `hardware_read_only` — sending those as commands
  to real firmware needs a command channel on the STM32/ESP32 side that
  doesn't exist yet. Everything *reading* from hardware (telemetry, ECU
  status, CAN frames, events) is fully wired.
- Voice is typed-only; no speech recognition is included.
- ARI is deliberately rule-based/templated, not an LLM — per the
  architecture doc's explicit requirement that it never invent a vehicle
  condition.
