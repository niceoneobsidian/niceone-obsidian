"""Tenant-scoped source registry and lifecycle control plane."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Protocol

import psycopg


class SourceStatus(StrEnum):
    REGISTERED = "registered"
    ENABLED = "enabled"
    PAUSED = "paused"
    DEGRADED = "degraded"
    DISABLED = "disabled"


_ALLOWED_TRANSITIONS: dict[SourceStatus, frozenset[SourceStatus]] = {
    SourceStatus.REGISTERED: frozenset({SourceStatus.ENABLED, SourceStatus.DISABLED}),
    SourceStatus.ENABLED: frozenset(
        {SourceStatus.PAUSED, SourceStatus.DEGRADED, SourceStatus.DISABLED}
    ),
    SourceStatus.PAUSED: frozenset({SourceStatus.ENABLED, SourceStatus.DISABLED}),
    SourceStatus.DEGRADED: frozenset(
        {SourceStatus.ENABLED, SourceStatus.PAUSED, SourceStatus.DISABLED}
    ),
    SourceStatus.DISABLED: frozenset({SourceStatus.REGISTERED}),
}


@dataclass(frozen=True)
class SourceDefinition:
    source_id: str
    tenant_id: str
    workspace_id: str
    provider: str
    mode: str
    enabled: bool = True
    config: dict[str, Any] | None = None
    credential_id: str | None = None
    updated_at: datetime | None = None
    status: SourceStatus | str | None = None
    poll_interval_seconds: float | None = None
    capabilities: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.tenant_id or not self.workspace_id or not self.source_id or not self.provider:
            raise ValueError("tenant_id, workspace_id, source_id, and provider are required")
        if self.mode not in {"poll", "webhook", "push"}:
            raise ValueError("unsupported source mode")
        if self.poll_interval_seconds is not None and self.poll_interval_seconds <= 0:
            raise ValueError("poll_interval_seconds must be positive")
        status = SourceStatus(self.status) if self.status is not None else (
            SourceStatus.ENABLED if self.enabled else SourceStatus.DISABLED
        )
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "enabled", status == SourceStatus.ENABLED)

    def transition(self, target: SourceStatus | str) -> SourceDefinition:
        target_status = SourceStatus(target)
        current = SourceStatus(self.status or SourceStatus.ENABLED)
        if target_status == current:
            return self
        if target_status not in _ALLOWED_TRANSITIONS[current]:
            raise ValueError(f"invalid source lifecycle transition: {current} -> {target_status}")
        return SourceDefinition(
            source_id=self.source_id,
            tenant_id=self.tenant_id,
            workspace_id=self.workspace_id,
            provider=self.provider,
            mode=self.mode,
            enabled=target_status == SourceStatus.ENABLED,
            config=dict(self.config or {}),
            credential_id=self.credential_id,
            status=target_status,
            poll_interval_seconds=self.poll_interval_seconds,
            capabilities=self.capabilities,
        )


class SourceRegistryStore(Protocol):
    def put(self, source: SourceDefinition) -> None: ...
    def get(self, tenant_id: str, workspace_id: str, source_id: str) -> SourceDefinition | None: ...
    def list(self, tenant_id: str, workspace_id: str) -> tuple[SourceDefinition, ...]: ...
    def delete(self, tenant_id: str, workspace_id: str, source_id: str) -> None: ...


class SQLiteSourceRegistry:
    def __init__(self, path: str = ":memory:") -> None:
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._db.execute(
            """
            CREATE TABLE IF NOT EXISTS source_registry (
                tenant_id TEXT NOT NULL,
                workspace_id TEXT NOT NULL,
                source_id TEXT NOT NULL,
                provider TEXT NOT NULL,
                mode TEXT NOT NULL,
                enabled INTEGER NOT NULL,
                config TEXT NOT NULL,
                credential_id TEXT,
                updated_at TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'enabled',
                poll_interval_seconds REAL,
                capabilities TEXT NOT NULL DEFAULT '[]',
                PRIMARY KEY (tenant_id, workspace_id, source_id)
            )
            """
        )
        columns = {row[1] for row in self._db.execute("PRAGMA table_info(source_registry)")}
        if "status" not in columns:
            self._db.execute(
                "ALTER TABLE source_registry ADD COLUMN status TEXT NOT NULL DEFAULT 'enabled'"
            )
        if "poll_interval_seconds" not in columns:
            self._db.execute("ALTER TABLE source_registry ADD COLUMN poll_interval_seconds REAL")
        if "capabilities" not in columns:
            self._db.execute(
                "ALTER TABLE source_registry ADD COLUMN capabilities TEXT NOT NULL DEFAULT '[]'"
            )
        self._db.commit()

    @staticmethod
    def _source(row: tuple[Any, ...]) -> SourceDefinition:
        return SourceDefinition(
            source_id=row[0],
            tenant_id=row[1],
            workspace_id=row[2],
            provider=row[3],
            mode=row[4],
            enabled=bool(row[5]),
            config=json.loads(row[6]),
            credential_id=row[7],
            updated_at=datetime.fromisoformat(row[8]),
            status=row[9],
            poll_interval_seconds=row[10],
            capabilities=tuple(json.loads(row[11])),
        )

    def put(self, source: SourceDefinition) -> None:
        now = source.updated_at or datetime.now(UTC)
        self._db.execute(
            """
            INSERT INTO source_registry
                (tenant_id, workspace_id, source_id, provider, mode, enabled, config,
                 credential_id, updated_at, status, poll_interval_seconds, capabilities)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(tenant_id, workspace_id, source_id) DO UPDATE SET
                provider=excluded.provider, mode=excluded.mode, enabled=excluded.enabled,
                config=excluded.config, credential_id=excluded.credential_id,
                updated_at=excluded.updated_at, status=excluded.status,
                poll_interval_seconds=excluded.poll_interval_seconds,
                capabilities=excluded.capabilities
            """,
            (
                source.tenant_id,
                source.workspace_id,
                source.source_id,
                source.provider,
                source.mode,
                int(source.enabled),
                json.dumps(source.config or {}, sort_keys=True),
                source.credential_id,
                now.isoformat(),
                str(source.status),
                source.poll_interval_seconds,
                json.dumps(sorted(source.capabilities)),
            ),
        )
        self._db.commit()

    def get(self, tenant_id: str, workspace_id: str, source_id: str) -> SourceDefinition | None:
        row = self._db.execute(
            """
            SELECT source_id, tenant_id, workspace_id, provider, mode, enabled, config,
                   credential_id, updated_at, status, poll_interval_seconds, capabilities
            FROM source_registry
            WHERE tenant_id=? AND workspace_id=? AND source_id=?
            """,
            (tenant_id, workspace_id, source_id),
        ).fetchone()
        return None if row is None else self._source(row)

    def list(self, tenant_id: str, workspace_id: str) -> tuple[SourceDefinition, ...]:
        rows = self._db.execute(
            """
            SELECT source_id, tenant_id, workspace_id, provider, mode, enabled, config,
                   credential_id, updated_at, status, poll_interval_seconds, capabilities
            FROM source_registry
            WHERE tenant_id=? AND workspace_id=?
            ORDER BY source_id
            """,
            (tenant_id, workspace_id),
        ).fetchall()
        return tuple(self._source(row) for row in rows)

    def delete(self, tenant_id: str, workspace_id: str, source_id: str) -> None:
        self._db.execute(
            "DELETE FROM source_registry WHERE tenant_id=? AND workspace_id=? AND source_id=?",
            (tenant_id, workspace_id, source_id),
        )
        self._db.commit()


class PostgresSourceRegistry:
    """Production registry using the Phase B PostgreSQL source boundary."""

    def __init__(self, connection: psycopg.Connection[Any]) -> None:
        self._connection = connection

    @staticmethod
    def _source(row: tuple[Any, ...]) -> SourceDefinition:
        return SourceDefinition(
            source_id=row[0],
            tenant_id=row[1],
            workspace_id=row[2],
            provider=row[3],
            mode=row[4],
            enabled=bool(row[5]),
            config=dict(row[6] or {}),
            credential_id=row[7],
            updated_at=row[8],
            status=row[9],
            poll_interval_seconds=row[10],
            capabilities=tuple(row[11] or ()),
        )

    def put(self, source: SourceDefinition) -> None:
        with self._connection.transaction(), self._connection.cursor() as cur:
            cur.execute(
                """
                INSERT INTO source_registry
                    (tenant_id, workspace_id, source_id, provider, mode, enabled, config,
                     credential_id, updated_at, status, poll_interval_seconds, capabilities)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (tenant_id, workspace_id, source_id) DO UPDATE SET
                    provider=EXCLUDED.provider, mode=EXCLUDED.mode, enabled=EXCLUDED.enabled,
                    config=EXCLUDED.config, credential_id=EXCLUDED.credential_id,
                    updated_at=EXCLUDED.updated_at, status=EXCLUDED.status,
                    poll_interval_seconds=EXCLUDED.poll_interval_seconds,
                    capabilities=EXCLUDED.capabilities
                """,
                (
                    source.tenant_id,
                    source.workspace_id,
                    source.source_id,
                    source.provider,
                    source.mode,
                    source.enabled,
                    json.dumps(source.config or {}, sort_keys=True),
                    source.credential_id,
                    source.updated_at or datetime.now(UTC),
                    str(source.status),
                    source.poll_interval_seconds,
                    list(source.capabilities),
                ),
            )

    def get(self, tenant_id: str, workspace_id: str, source_id: str) -> SourceDefinition | None:
        with self._connection.cursor() as cur:
            cur.execute(
                """
                SELECT source_id, tenant_id, workspace_id, provider, mode, enabled, config,
                       credential_id, updated_at, status, poll_interval_seconds, capabilities
                FROM source_registry
                WHERE tenant_id=%s AND workspace_id=%s AND source_id=%s
                """,
                (tenant_id, workspace_id, source_id),
            )
            row = cur.fetchone()
        return None if row is None else self._source(row)

    def list(self, tenant_id: str, workspace_id: str) -> tuple[SourceDefinition, ...]:
        with self._connection.cursor() as cur:
            cur.execute(
                """
                SELECT source_id, tenant_id, workspace_id, source_id, provider, mode, enabled,
                       config, credential_id, updated_at, status, poll_interval_seconds, capabilities
                FROM source_registry
                WHERE tenant_id=%s AND workspace_id=%s
                ORDER BY source_id
                """.replace(
                    "SELECT source_id, tenant_id, workspace_id, source_id, provider",
                    "SELECT source_id, tenant_id, workspace_id, provider",
                ),
                (tenant_id, workspace_id),
            )
            rows = cur.fetchall()
        return tuple(self._source(row) for row in rows)

    def delete(self, tenant_id: str, workspace_id: str, source_id: str) -> None:
        with self._connection.transaction(), self._connection.cursor() as cur:
            cur.execute(
                "DELETE FROM source_registry WHERE tenant_id=%s AND workspace_id=%s AND source_id=%s",
                (tenant_id, workspace_id, source_id),
            )


class SourceControlAPI:
    """Tenant/workspace-scoped source lifecycle control surface."""

    def __init__(self, store: SourceRegistryStore) -> None:
        self._store = store

    def register(self, source: SourceDefinition) -> SourceDefinition:
        existing = self._store.get(source.tenant_id, source.workspace_id, source.source_id)
        if existing is not None and SourceStatus(existing.status or "") != SourceStatus.DISABLED:
            raise ValueError(f"source already registered: {source.source_id}")
        registered = SourceDefinition(
            source_id=source.source_id,
            tenant_id=source.tenant_id,
            workspace_id=source.workspace_id,
            provider=source.provider,
            mode=source.mode,
            enabled=source.enabled,
            config=source.config,
            credential_id=source.credential_id,
            status=source.status,
            poll_interval_seconds=source.poll_interval_seconds,
            capabilities=source.capabilities,
        )
        self._store.put(registered)
        return self.get(
            tenant_id=source.tenant_id,
            workspace_id=source.workspace_id,
            source_id=source.source_id,
        )

    def get(self, *, tenant_id: str, workspace_id: str, source_id: str) -> SourceDefinition:
        source = self._store.get(tenant_id, workspace_id, source_id)
        if source is None:
            raise KeyError(f"source not registered: {source_id}")
        return source

    def list(self, *, tenant_id: str, workspace_id: str) -> tuple[SourceDefinition, ...]:
        return self._store.list(tenant_id, workspace_id)

    def transition(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        source_id: str,
        target: SourceStatus | str,
    ) -> SourceDefinition:
        source = self.get(tenant_id=tenant_id, workspace_id=workspace_id, source_id=source_id)
        updated = source.transition(target)
        self._store.put(updated)
        return self.get(tenant_id=tenant_id, workspace_id=workspace_id, source_id=source_id)

    def enable(self, **scope: str) -> SourceDefinition:
        return self.transition(target=SourceStatus.ENABLED, **scope)

    def pause(self, **scope: str) -> SourceDefinition:
        return self.transition(target=SourceStatus.PAUSED, **scope)

    def degrade(self, **scope: str) -> SourceDefinition:
        return self.transition(target=SourceStatus.DEGRADED, **scope)

    def disable(self, **scope: str) -> SourceDefinition:
        return self.transition(target=SourceStatus.DISABLED, **scope)

    def set_enabled(
        self, *, tenant_id: str, workspace_id: str, source_id: str, enabled: bool
    ) -> SourceDefinition:
        return self.enable(
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            source_id=source_id,
        ) if enabled else self.disable(
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            source_id=source_id,
        )

    def delete(self, *, tenant_id: str, workspace_id: str, source_id: str) -> None:
        self.get(tenant_id=tenant_id, workspace_id=workspace_id, source_id=source_id)
        self._store.delete(tenant_id, workspace_id, source_id)
