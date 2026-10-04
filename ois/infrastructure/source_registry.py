"""Source registration and control plane for live source definitions."""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Protocol


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

    def __post_init__(self) -> None:
        if not self.tenant_id or not self.workspace_id or not self.source_id or not self.provider:
            raise ValueError("tenant_id, workspace_id, source_id, and provider are required")
        if self.mode not in {"poll", "webhook", "push"}:
            raise ValueError("unsupported source mode")


class SourceRegistryStore(Protocol):
    def put(self, source: SourceDefinition) -> None: ...
    def get(self, tenant_id: str, workspace_id: str, source_id: str) -> SourceDefinition | None: ...
    def list(self, tenant_id: str, workspace_id: str) -> tuple[SourceDefinition, ...]: ...
    def delete(self, tenant_id: str, workspace_id: str, source_id: str) -> None: ...


class SQLiteSourceRegistry:
    def __init__(self, path: str = ":memory:") -> None:
        self._db = sqlite3.connect(path)
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
                PRIMARY KEY (tenant_id, workspace_id, source_id)
            )
            """
        )
        self._db.commit()

    def put(self, source: SourceDefinition) -> None:
        import json

        now = source.updated_at or datetime.now(UTC)
        self._db.execute(
            """
            INSERT INTO source_registry
                (tenant_id, workspace_id, source_id, provider, mode, enabled, config,
                 credential_id, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(tenant_id, workspace_id, source_id) DO UPDATE SET
                provider=excluded.provider, mode=excluded.mode, enabled=excluded.enabled,
                config=excluded.config, credential_id=excluded.credential_id,
                updated_at=excluded.updated_at
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
            ),
        )
        self._db.commit()

    def get(self, tenant_id: str, workspace_id: str, source_id: str) -> SourceDefinition | None:
        import json

        row = self._db.execute(
            """
            SELECT source_id, tenant_id, workspace_id, provider, mode, enabled, config,
                   credential_id, updated_at
            FROM source_registry
            WHERE tenant_id=? AND workspace_id=? AND source_id=?
            """,
            (tenant_id, workspace_id, source_id),
        ).fetchone()
        if row is None:
            return None
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
        )

    def list(self, tenant_id: str, workspace_id: str) -> tuple[SourceDefinition, ...]:
        rows = self._db.execute(
            """
            SELECT source_id, tenant_id, workspace_id, provider, mode, enabled, config,
                   credential_id, updated_at
            FROM source_registry
            WHERE tenant_id=? AND workspace_id=?
            ORDER BY source_id
            """,
            (tenant_id, workspace_id),
        ).fetchall()
        import json

        return tuple(
            SourceDefinition(
                source_id=r[0],
                tenant_id=r[1],
                workspace_id=r[2],
                provider=r[3],
                mode=r[4],
                enabled=bool(r[5]),
                config=json.loads(r[6]),
                credential_id=r[7],
                updated_at=datetime.fromisoformat(r[8]),
            )
            for r in rows
        )

    def delete(self, tenant_id: str, workspace_id: str, source_id: str) -> None:
        self._db.execute(
            "DELETE FROM source_registry WHERE tenant_id=? AND workspace_id=? AND source_id=?",
            (tenant_id, workspace_id, source_id),
        )
        self._db.commit()


class SourceControlAPI:
    """Application control surface; all mutations require tenant/workspace scope."""

    def __init__(self, store: SourceRegistryStore) -> None:
        self._store = store

    def register(self, source: SourceDefinition) -> SourceDefinition:
        self._store.put(source)
        return self._store.get(source.tenant_id, source.workspace_id, source.source_id) or source

    def get(self, *, tenant_id: str, workspace_id: str, source_id: str) -> SourceDefinition:
        source = self._store.get(tenant_id, workspace_id, source_id)
        if source is None:
            raise KeyError(f"source not registered: {source_id}")
        return source

    def list(self, *, tenant_id: str, workspace_id: str) -> tuple[SourceDefinition, ...]:
        return self._store.list(tenant_id, workspace_id)

    def set_enabled(
        self, *, tenant_id: str, workspace_id: str, source_id: str, enabled: bool
    ) -> SourceDefinition:
        source = self.get(tenant_id=tenant_id, workspace_id=workspace_id, source_id=source_id)
        updated = SourceDefinition(
            source_id=source.source_id,
            tenant_id=source.tenant_id,
            workspace_id=source.workspace_id,
            provider=source.provider,
            mode=source.mode,
            enabled=enabled,
            config=source.config,
            credential_id=source.credential_id,
        )
        self._store.put(updated)
        return self.get(tenant_id=tenant_id, workspace_id=workspace_id, source_id=source_id)

    def delete(self, *, tenant_id: str, workspace_id: str, source_id: str) -> None:
        self.get(tenant_id=tenant_id, workspace_id=workspace_id, source_id=source_id)
        self._store.delete(tenant_id, workspace_id, source_id)
