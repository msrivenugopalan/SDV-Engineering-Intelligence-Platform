"""SQLite history — events, OTA, voice. High-rate telemetry is downsampled."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

from sdv_console.config import DATA_DIR, SQLITE_PATH
from sdv_console.core.event_manager import EventManager
from sdv_console.core.events import TELEMETRY_SAMPLE, VehicleEvent


class HistoryService:
    def __init__(self, events: EventManager, db_path: Path | None = None) -> None:
        self.events = events
        self.db_path = db_path or SQLITE_PATH
        self._lock = Lock()
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        self._init_db()
        events.subscribe(None, self._on_event)
        self.ready = True

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._lock:
            conn = self._connect()
            try:
                conn.executescript(
                    """
                    CREATE TABLE IF NOT EXISTS events (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        event_type TEXT NOT NULL,
                        ecu TEXT,
                        severity TEXT,
                        source TEXT,
                        correlation_id TEXT,
                        payload TEXT
                    );
                    CREATE TABLE IF NOT EXISTS telemetry (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        engine_temp REAL,
                        battery_voltage REAL,
                        battery_current REAL,
                        cabin_temp REAL
                    );
                    CREATE TABLE IF NOT EXISTS ota_history (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        target_ecu TEXT,
                        from_version TEXT,
                        to_version TEXT,
                        result TEXT
                    );
                    CREATE TABLE IF NOT EXISTS voice_commands (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        timestamp TEXT NOT NULL,
                        utterance TEXT,
                        parsed TEXT,
                        result TEXT
                    );
                    CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
                    CREATE INDEX IF NOT EXISTS idx_events_ecu ON events(ecu);
                    """
                )
                conn.commit()
            finally:
                conn.close()

    def _on_event(self, event: VehicleEvent) -> None:
        if event.event_type in {TELEMETRY_SAMPLE, "CAN_FRAME"}:
            return
        self.insert_event(event)

    def insert_event(self, event: VehicleEvent) -> None:
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    INSERT INTO events(timestamp, event_type, ecu, severity, source, correlation_id, payload)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        event.timestamp,
                        event.event_type,
                        event.ecu,
                        event.severity,
                        event.source,
                        event.correlation_id,
                        json.dumps(event.payload),
                    ),
                )
                conn.commit()
            finally:
                conn.close()

    def insert_telemetry_sample(self, telemetry: dict) -> None:
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    INSERT INTO telemetry(timestamp, engine_temp, battery_voltage, battery_current, cabin_temp)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        datetime.now(timezone.utc).isoformat(),
                        telemetry.get("engine_temp"),
                        telemetry.get("battery_voltage"),
                        telemetry.get("battery_current"),
                        telemetry.get("cabin_temp"),
                    ),
                )
                conn.commit()
            finally:
                conn.close()

    def insert_ota(self, target_ecu: str, from_version: str, to_version: str, result: str) -> None:
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    INSERT INTO ota_history(timestamp, target_ecu, from_version, to_version, result)
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        datetime.now(timezone.utc).isoformat(),
                        target_ecu,
                        from_version,
                        to_version,
                        result,
                    ),
                )
                conn.commit()
            finally:
                conn.close()

    def insert_voice(self, utterance: str, parsed: str, result: str) -> None:
        with self._lock:
            conn = self._connect()
            try:
                conn.execute(
                    """
                    INSERT INTO voice_commands(timestamp, utterance, parsed, result)
                    VALUES (?, ?, ?, ?)
                    """,
                    (datetime.now(timezone.utc).isoformat(), utterance, parsed, result),
                )
                conn.commit()
            finally:
                conn.close()

    def query_events(
        self,
        *,
        ecu: str | None = None,
        event_type: str | None = None,
        severity: str | None = None,
        limit: int = 200,
    ) -> list[dict]:
        sql = "SELECT * FROM events WHERE 1=1"
        params: list = []
        if ecu:
            sql += " AND ecu = ?"
            params.append(ecu)
        if event_type:
            sql += " AND event_type = ?"
            params.append(event_type)
        if severity:
            sql += " AND severity = ?"
            params.append(severity)
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute(sql, params).fetchall()
                return [dict(r) for r in rows]
            finally:
                conn.close()

    def query_ota(self, limit: int = 20) -> list[dict]:
        with self._lock:
            conn = self._connect()
            try:
                rows = conn.execute(
                    "SELECT * FROM ota_history ORDER BY id DESC LIMIT ?", (limit,)
                ).fetchall()
                return [dict(r) for r in rows]
            finally:
                conn.close()
