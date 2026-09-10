"""SQLite persistence (architecture doc §17) — a real data layer instead of
everything disappearing when the app closes.

Uses one persistent connection (WAL mode) instead of opening/closing per
call — the connection is reused under a lock, which matters because inserts
happen on nearly every event and this runs on the same thread as the UI.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

from sdv_console.core.event_bus import EventBus
from sdv_console.core.models import VehicleEvent

DATA_DIR = Path(__file__).resolve().parent.parent.parent / "data"
DB_PATH = DATA_DIR / "sdv_history.sqlite"


class HistoryService:
    def __init__(self, events: EventBus, db_path: Path | None = None) -> None:
        self.events = events
        self.db_path = db_path or DB_PATH
        self._lock = Lock()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        try:
            self._conn.execute("PRAGMA journal_mode=WAL")
            self._conn.execute("PRAGMA synchronous=NORMAL")
        except sqlite3.Error:
            pass
        self._init_db()
        events.subscribe(None, self._on_event)
        self.ready = True

    def close(self) -> None:
        with self._lock:
            try:
                self._conn.close()
            except sqlite3.Error:
                pass

    def _init_db(self) -> None:
        with self._lock:
            self._conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    ecu TEXT,
                    severity TEXT,
                    source TEXT,
                    payload TEXT
                );
                CREATE TABLE IF NOT EXISTS ota_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    target_ecu TEXT,
                    from_version TEXT,
                    to_version TEXT,
                    result TEXT
                );
                CREATE TABLE IF NOT EXISTS voice_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    utterance TEXT,
                    reply TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type);
                CREATE INDEX IF NOT EXISTS idx_events_ecu ON events(ecu);
                """
            )
            self._conn.commit()

    def _on_event(self, event: VehicleEvent) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO events(timestamp, event_type, ecu, severity, source, payload) VALUES (?, ?, ?, ?, ?, ?)",
                (event.timestamp, event.event_type, event.ecu, event.severity, event.source, json.dumps(event.payload)),
            )
            self._conn.commit()

    def insert_ota(self, target_ecu: str, from_version: str, to_version: str, result: str) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO ota_history(timestamp, target_ecu, from_version, to_version, result) VALUES (?, ?, ?, ?, ?)",
                (datetime.now(timezone.utc).isoformat(), target_ecu, from_version, to_version, result),
            )
            self._conn.commit()

    def insert_voice(self, utterance: str, reply: str) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT INTO voice_log(timestamp, utterance, reply) VALUES (?, ?, ?)",
                (datetime.now(timezone.utc).isoformat(), utterance, reply),
            )
            self._conn.commit()

    def query_events(self, ecu: str | None = None, event_type: str | None = None, limit: int = 150) -> list[dict]:
        sql = "SELECT * FROM events WHERE 1=1"
        params: list = []
        if ecu:
            sql += " AND ecu = ?"
            params.append(ecu)
        if event_type:
            sql += " AND event_type = ?"
            params.append(event_type)
        sql += " ORDER BY id DESC LIMIT ?"
        params.append(limit)
        with self._lock:
            rows = self._conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]

    def query_ota(self, limit: int = 20) -> list[dict]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM ota_history ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
            return [dict(r) for r in rows]
