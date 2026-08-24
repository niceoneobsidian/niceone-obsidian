"""Append-only attribution persistence."""
from __future__ import annotations

import sqlite3
from pathlib import Path
from .attribution import AttributionResult


class SQLiteAttributionStore:
    def __init__(self, path: str | Path = ":memory:") -> None:
        self._db = sqlite3.connect(str(path))
        self._db.execute(
            """CREATE TABLE IF NOT EXISTS attribution_results (
                conversion_id TEXT NOT NULL, touchpoint_id TEXT NOT NULL,
                credit REAL NOT NULL, total_value REAL NOT NULL,
                confidence REAL NOT NULL, PRIMARY KEY(conversion_id, touchpoint_id)
            )"""
        )
        self._db.commit()

    def append(self, result: AttributionResult) -> int:
        inserted = 0
        for touchpoint_id, credit in result.credited_touchpoints:
            cursor = self._db.execute(
                """INSERT OR IGNORE INTO attribution_results
                (conversion_id, touchpoint_id, credit, total_value, confidence)
                VALUES (?, ?, ?, ?, ?)""",
                (result.conversion_id, touchpoint_id, credit,
                 result.total_value, result.confidence),
            )
            inserted += int(cursor.rowcount == 1)
        self._db.commit()
        return inserted

    def get(self, conversion_id: str) -> list[tuple[str, float]]:
        rows = self._db.execute(
            "SELECT touchpoint_id, credit FROM attribution_results "
            "WHERE conversion_id=? ORDER BY touchpoint_id", (conversion_id,)
        ).fetchall()
        return [(str(row[0]), float(row[1])) for row in rows]

    def close(self) -> None:
        self._db.close()
