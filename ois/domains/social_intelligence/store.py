"""Durable G1 persistence for derived Social Intelligence artifacts."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from ois.domains.social_growth.schemas import (
    AudienceProfile,
    CompetitorProfile,
    CreativePattern,
    SocialResearchBrief,
    SocialSignal,
)


class IntelligenceStore(Protocol):
    """Storage contract for derived Social Intelligence artifacts."""

    def put_audience_profile(self, profile: AudienceProfile) -> None: ...
    def put_competitor_profile(self, profile: CompetitorProfile) -> None: ...
    def put_signal(self, signal: SocialSignal) -> None: ...
    def put_creative_pattern(self, pattern: CreativePattern) -> None: ...
    def put_research_brief(self, brief: SocialResearchBrief) -> int: ...
    def list_audience_profiles(self, *, limit: int = 100) -> list[AudienceProfile]: ...
    def list_competitor_profiles(self, *, limit: int = 100) -> list[CompetitorProfile]: ...
    def list_signals(
        self, *, signal_type: str | None = None, limit: int = 100
    ) -> list[SocialSignal]: ...
    def list_creative_patterns(self, *, limit: int = 100) -> list[CreativePattern]: ...
    def list_research_briefs(self, *, limit: int = 100) -> list[SocialResearchBrief]: ...


_TABLES = {
    "audience_profiles": "audience_id",
    "competitor_profiles": "competitor_id",
    "signals": "signal_id",
    "creative_patterns": "pattern_id",
}


class SQLiteIntelligenceStore:
    """Deterministic SQLite reference implementation for local/test execution."""

    def __init__(self, path: str | Path = ":memory:") -> None:
        self._connection = sqlite3.connect(str(path))
        self._connection.row_factory = sqlite3.Row
        self._connection.execute("PRAGMA foreign_keys = ON")
        for table, key in _TABLES.items():
            self._connection.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {table} (
                    {key} TEXT PRIMARY KEY,
                    payload TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS research_briefs (
                brief_id INTEGER PRIMARY KEY AUTOINCREMENT,
                query TEXT NOT NULL,
                payload TEXT NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )
        self._connection.commit()

    def _upsert(self, table: str, key_column: str, key: str, payload: dict) -> None:
        self._connection.execute(
            f"""
            INSERT INTO {table} ({key_column}, payload, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT({key_column}) DO UPDATE SET
                payload = excluded.payload,
                updated_at = excluded.updated_at
            """,
            (key, json.dumps(payload, sort_keys=True), datetime.now(UTC).isoformat()),
        )
        self._connection.commit()

    def put_audience_profile(self, profile: AudienceProfile) -> None:
        self._upsert(
            "audience_profiles",
            "audience_id",
            profile.audience_id,
            profile.model_dump(mode="json"),
        )

    def put_competitor_profile(self, profile: CompetitorProfile) -> None:
        self._upsert(
            "competitor_profiles",
            "competitor_id",
            profile.competitor_id,
            profile.model_dump(mode="json"),
        )

    def put_signal(self, signal: SocialSignal) -> None:
        self._upsert(
            "signals", "signal_id", signal.signal_id, signal.model_dump(mode="json")
        )

    def put_creative_pattern(self, pattern: CreativePattern) -> None:
        self._upsert(
            "creative_patterns",
            "pattern_id",
            pattern.pattern_id,
            pattern.model_dump(mode="json"),
        )

    def put_research_brief(self, brief: SocialResearchBrief) -> int:
        cursor = self._connection.execute(
            "INSERT INTO research_briefs (query, payload, created_at) VALUES (?, ?, ?)",
            (
                brief.query,
                json.dumps(brief.model_dump(mode="json"), sort_keys=True),
                datetime.now(UTC).isoformat(),
            ),
        )
        self._connection.commit()
        if cursor.lastrowid is None:
            raise RuntimeError("database did not return a row id")
        return int(cursor.lastrowid)

    def list_audience_profiles(self, *, limit: int = 100) -> list[AudienceProfile]:
        rows = self._connection.execute(
            "SELECT payload FROM audience_profiles ORDER BY audience_id LIMIT ?", (limit,)
        ).fetchall()
        return [AudienceProfile.model_validate(json.loads(row["payload"])) for row in rows]

    def list_competitor_profiles(self, *, limit: int = 100) -> list[CompetitorProfile]:
        rows = self._connection.execute(
            "SELECT payload FROM competitor_profiles ORDER BY competitor_id LIMIT ?", (limit,)
        ).fetchall()
        return [CompetitorProfile.model_validate(json.loads(row["payload"])) for row in rows]

    def list_signals(
        self, *, signal_type: str | None = None, limit: int = 100
    ) -> list[SocialSignal]:
        rows = self._connection.execute(
            "SELECT payload FROM signals ORDER BY signal_id LIMIT ?", (limit,)
        ).fetchall()
        signals = [SocialSignal.model_validate(json.loads(row["payload"])) for row in rows]
        return [
            signal
            for signal in signals
            if signal_type is None or signal.signal_type == signal_type
        ]

    def list_creative_patterns(self, *, limit: int = 100) -> list[CreativePattern]:
        rows = self._connection.execute(
            "SELECT payload FROM creative_patterns ORDER BY pattern_id LIMIT ?", (limit,)
        ).fetchall()
        return [CreativePattern.model_validate(json.loads(row["payload"])) for row in rows]

    def list_research_briefs(self, *, limit: int = 100) -> list[SocialResearchBrief]:
        rows = self._connection.execute(
            "SELECT payload FROM research_briefs ORDER BY brief_id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [SocialResearchBrief.model_validate(json.loads(row["payload"])) for row in rows]

    def put_many_signals(self, signals: Iterable[SocialSignal]) -> int:
        count = 0
        for signal in signals:
            self.put_signal(signal)
            count += 1
        return count

    def close(self) -> None:
        self._connection.close()
