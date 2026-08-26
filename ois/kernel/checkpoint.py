from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from pathlib import Path
from threading import RLock
from typing import Protocol
from uuid import UUID

from .state import ExecutionContext


class CheckpointError(Exception):
    """Base checkpoint error."""


class CheckpointNotFound(CheckpointError):
    """Raised when a checkpoint does not exist."""


class CheckpointConflict(CheckpointError):
    """Raised when a stale execution context attempts to overwrite a newer checkpoint."""


class CheckpointStore(Protocol):
    def save(self, context: ExecutionContext) -> None: ...
    def load(self, execution_id: UUID) -> ExecutionContext: ...
    def delete(self, execution_id: UUID) -> None: ...


class InMemoryCheckpointStore:
    def __init__(self) -> None:
        self._store: dict[UUID, ExecutionContext] = {}
        self._lock = RLock()

    def save(self, context: ExecutionContext) -> None:
        context.touch()
        with self._lock:
            current = self._store.get(context.identity.execution_id)
            expected = context.checkpoint_version
            if current is not None and current.checkpoint_version != expected:
                raise CheckpointConflict("Checkpoint version is stale")
            context.checkpoint_version += 1
            self._store[context.identity.execution_id] = deepcopy(context)

    def load(self, execution_id: UUID) -> ExecutionContext:
        with self._lock:
            context = self._store.get(execution_id)
            if context is None:
                raise CheckpointNotFound(f"No checkpoint for execution {execution_id}")
            return deepcopy(context)

    def delete(self, execution_id: UUID) -> None:
        with self._lock:
            self._store.pop(execution_id, None)

    def exists(self, execution_id: UUID) -> bool:
        with self._lock:
            return execution_id in self._store

    def snapshot(self, execution_id: UUID) -> dict[str, object]:
        context = self.load(execution_id)
        return {
            "execution_id": str(context.identity.execution_id),
            "status": context.status.value,
            "created_at": context.created_at.isoformat(),
            "updated_at": context.updated_at.isoformat(),
            "state": asdict(context),
        }


class JsonFileCheckpointStore:
    """Durable filesystem checkpoint store with optimistic version checks."""

    def __init__(self, root_path: str = ".ois/checkpoints") -> None:
        self._root = Path(root_path)
        self._root.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()

    def _path(self, execution_id: UUID | str) -> Path:
        return self._root / f"{execution_id}.json"

    def save(self, context: ExecutionContext) -> None:
        import json

        with self._lock:
            current = self.load(context.identity.execution_id) if self.exists(context.identity.execution_id) else None
            if current is not None and current.checkpoint_version != context.checkpoint_version:
                raise CheckpointConflict("Checkpoint version is stale")
            context.touch()
            context.checkpoint_version += 1
            path = self._path(context.identity.execution_id)
            temporary = path.with_suffix(".tmp")
            temporary.write_text(json.dumps(context.to_dict(), indent=2, sort_keys=True))
            temporary.replace(path)

    def load(self, execution_id: UUID) -> ExecutionContext:
        import json

        path = self._path(execution_id)
        if not path.exists():
            raise CheckpointNotFound(str(execution_id))
        with self._lock:
            return ExecutionContext.from_dict(json.loads(path.read_text()))

    def exists(self, execution_id: UUID) -> bool:
        return self._path(execution_id).exists()

    def delete(self, execution_id: UUID) -> None:
        with self._lock:
            path = self._path(execution_id)
            if path.exists():
                path.unlink()

    def list_execution_ids(self) -> list[str]:
        return [path.stem for path in self._root.glob("*.json")]


class PostgresCheckpointStore:
    """PostgreSQL checkpoint backend with transactional optimistic concurrency."""

    def __init__(self, dsn: str, *, connect_timeout: int = 10) -> None:
        try:
            import psycopg
        except ImportError as exc:
            raise RuntimeError("PostgreSQL backend requires the psycopg package") from exc
        self._psycopg = psycopg
        self._dsn = dsn
        self._connect_timeout = connect_timeout

    def _connection(self):
        return self._psycopg.connect(self._dsn, connect_timeout=self._connect_timeout)

    def save(self, context: ExecutionContext) -> None:
        import json

        context.touch()
        execution_id = context.identity.execution_id
        expected = context.checkpoint_version
        next_version = expected + 1
        payload = context.to_dict()
        payload["checkpoint_version"] = next_version
        with self._connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (str(execution_id),))
                cursor.execute(
                    "SELECT checkpoint_version FROM ois_checkpoints WHERE execution_id=%s FOR UPDATE",
                    (execution_id,),
                )
                row = cursor.fetchone()
                if row is None:
                    if expected != 0:
                        raise CheckpointConflict("Checkpoint does not exist at expected version")
                    cursor.execute(
                        """
                        INSERT INTO ois_checkpoints(execution_id, tenant_id, checkpoint_version, state, created_at, updated_at)
                        VALUES(%s,%s,%s,%s::jsonb,%s,%s)
                        """,
                        (execution_id, context.identity.tenant_id, next_version, json.dumps(payload), context.created_at, context.updated_at),
                    )
                else:
                    if int(row[0]) != expected:
                        raise CheckpointConflict(f"Expected checkpoint version {expected}, found {row[0]}")
                    cursor.execute(
                        """
                        UPDATE ois_checkpoints
                        SET tenant_id=%s, checkpoint_version=%s, state=%s::jsonb, updated_at=%s
                        WHERE execution_id=%s AND checkpoint_version=%s
                        """,
                        (context.identity.tenant_id, next_version, json.dumps(payload), context.updated_at, execution_id, expected),
                    )
                    if cursor.rowcount != 1:
                        raise CheckpointConflict("Concurrent checkpoint update detected")
        context.checkpoint_version = next_version

    def load(self, execution_id: UUID) -> ExecutionContext:
        with self._connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT state FROM ois_checkpoints WHERE execution_id=%s", (execution_id,))
                row = cursor.fetchone()
        if row is None:
            raise CheckpointNotFound(f"No checkpoint for execution {execution_id}")
        return ExecutionContext.from_dict(row[0])

    def delete(self, execution_id: UUID) -> None:
        with self._connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("DELETE FROM ois_checkpoints WHERE execution_id=%s", (execution_id,))

    def exists(self, execution_id: UUID) -> bool:
        with self._connection() as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1 FROM ois_checkpoints WHERE execution_id=%s", (execution_id,))
                return cursor.fetchone() is not None


class CheckpointManager:
    def __init__(self, store: CheckpointStore) -> None:
        self.store = store

    def save(self, context: ExecutionContext) -> None:
        self.store.save(context)

    def load(self, execution_id: UUID) -> ExecutionContext:
        return self.store.load(execution_id)

    def delete(self, execution_id: UUID) -> None:
        self.store.delete(execution_id)
