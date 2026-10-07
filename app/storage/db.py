"""Thin SQLite data-access layer used by HarvestController."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Dict, List


class Database:
    def __init__(self, db_path: Path, schema_path: Path) -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_schema(Path(schema_path))

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, timeout=10, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_schema(self, schema_path: Path) -> None:
        with self._connect() as conn:
            conn.executescript(schema_path.read_text())

    def insert_session(self, session: Dict[str, Any]) -> int:
        with self._connect() as conn:
            cur = conn.execute(
                """
                INSERT INTO harvest_sessions
                    (branch_id, maturity_class, confidence, frequency_hz, amplitude_mm,
                     duration_target_s, duration_actual_s, harvested_mass_g, status,
                     operator_override, image_url, ended_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session["branch_id"],
                    session.get("maturity_class"),
                    session.get("confidence"),
                    session.get("frequency_hz"),
                    session.get("amplitude_mm"),
                    session.get("duration_target_s"),
                    session.get("duration_actual_s"),
                    session.get("harvested_mass_g"),
                    session["status"],
                    int(bool(session.get("operator_override"))),
                    session.get("image_url"),
                    session["ended_at"],
                ),
            )
            return int(cur.lastrowid)

    def fetch_sessions(self, limit: int = 20) -> List[Dict[str, Any]]:
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT * FROM harvest_sessions ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(row) for row in rows]

    def log_alert(self, severity: str, code: str, message: str, raised_at: str) -> None:
        with self._connect() as conn:
            conn.execute(
                "INSERT INTO alerts_log (severity, code, message, raised_at) VALUES (?, ?, ?, ?)",
                (severity, code, message, raised_at),
            )
