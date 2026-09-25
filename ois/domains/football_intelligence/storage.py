"""Small durable SQLite store for the Football Intelligence origin layer.

This is a local/dev persistence adapter. Production OIS persistence should map the
same records to the platform's governed PostgreSQL/evidence services.
"""
from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

from .origin import FixtureRecord, PredictionRecord


class FootballStore:
    def __init__(self, path: str | Path = "data/football_intelligence.db") -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.init()

    def init(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS fixtures (
                fixture_id TEXT PRIMARY KEY, competition TEXT NOT NULL, kickoff_at TEXT NOT NULL,
                home_team_id TEXT NOT NULL, home_team TEXT NOT NULL, away_team_id TEXT NOT NULL,
                away_team TEXT NOT NULL, home_goals INTEGER, away_goals INTEGER,
                home_xg REAL, away_xg REAL, status TEXT NOT NULL, source_id TEXT NOT NULL,
                observed_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS predictions (
                fixture_id TEXT NOT NULL, created_at TEXT NOT NULL, model_version TEXT NOT NULL,
                home REAL NOT NULL, draw REAL NOT NULL, away REAL NOT NULL,
                expected_home_goals REAL NOT NULL, expected_away_goals REAL NOT NULL,
                abstain INTEGER NOT NULL, evidence_ids TEXT NOT NULL,
                PRIMARY KEY (fixture_id, model_version)
            );
            CREATE INDEX IF NOT EXISTS idx_fixtures_kickoff ON fixtures(kickoff_at);
            CREATE INDEX IF NOT EXISTS idx_predictions_created ON predictions(created_at);
            """
        )
        self.conn.commit()

    def upsert_fixtures(self, fixtures: list[FixtureRecord]) -> None:
        self.conn.executemany(
            """INSERT INTO fixtures VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(fixture_id) DO UPDATE SET
               competition=excluded.competition,kickoff_at=excluded.kickoff_at,
               home_goals=excluded.home_goals,away_goals=excluded.away_goals,
               home_xg=excluded.home_xg,away_xg=excluded.away_xg,status=excluded.status,
               source_id=excluded.source_id,observed_at=excluded.observed_at""",
            [(
                f.fixture_id, f.competition, f.kickoff_at.isoformat(), f.home_team_id, f.home_team,
                f.away_team_id, f.away_team, f.home_goals, f.away_goals, f.home_xg, f.away_xg,
                f.status, f.source_id, f.observed_at.isoformat()
            ) for f in fixtures],
        )
        self.conn.commit()

    def save_prediction(self, prediction: PredictionRecord) -> None:
        self.conn.execute(
            """INSERT OR REPLACE INTO predictions VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                prediction.fixture_id, prediction.created_at.isoformat(), prediction.model_version,
                prediction.home, prediction.draw, prediction.away, prediction.expected_home_goals,
                prediction.expected_away_goals, int(prediction.abstain), json.dumps(prediction.evidence_ids),
            ),
        )
        self.conn.commit()

    def recent_completed(self, limit: int = 1000) -> list[FixtureRecord]:
        rows = self.conn.execute("SELECT * FROM fixtures WHERE home_goals IS NOT NULL ORDER BY kickoff_at LIMIT ?", (limit,)).fetchall()
        return [FixtureRecord(
            fixture_id=r["fixture_id"], competition=r["competition"], kickoff_at=datetime.fromisoformat(r["kickoff_at"]),
            home_team_id=r["home_team_id"], home_team=r["home_team"], away_team_id=r["away_team_id"], away_team=r["away_team"],
            home_goals=r["home_goals"], away_goals=r["away_goals"], home_xg=r["home_xg"], away_xg=r["away_xg"],
            status=r["status"], source_id=r["source_id"], observed_at=datetime.fromisoformat(r["observed_at"])
        ) for r in rows]

    def close(self) -> None:
        self.conn.close()
