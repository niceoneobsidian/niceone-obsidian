from __future__ import annotations

import hashlib
import json
import sqlite3
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


class CheckpointStore(Protocol):
    def save(self, context: ExecutionContext) -> None: ...

    def load(self, execution_id: UUID) -> ExecutionContext: ...

    def delete(self, execution_id: UUID) -> None: ...


class InMemoryCheckpointStore:
    """Reference process-local checkpoint implementation."""

    def __init__(self) -> None:
        self._store: dict[UUID, ExecutionContext] = {}
        self._lock = RLock()

    def save(self, context: ExecutionContext) -> None:
        context.touch()
        execution_id = context.identity.execution_id
        with self._lock:
            self._store[execution_id] = deepcopy(context)

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
            "state": context.to_dict(),
        }


class JsonFileCheckpointStore:
    """Durable filesystem-backed checkpoint store."""

    def __init__(self, root_path: str = ".ois/checkpoints") -> None:
        self._root = Path(root_path)
        self._root.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()

    def _path(self, execution_id: UUID | str) -> Path:
        return self._root / f"{execution_id}.json"

    def save(self, context: ExecutionContext) -> None:
        payload = context.to_dict()
        serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        envelope = {
            "schema_version": 1,
            "state_hash": hashlib.sha256(serialized.encode()).hexdigest(),
            "state": payload,
        }
        with self._lock:
            path = self._path(context.identity.execution_id)
            temporary = path.with_suffix(".tmp")
            temporary.write_text(json.dumps(envelope, indent=2, sort_keys=True))
            temporary.replace(path)

    def load(self, execution_id: UUID) -> ExecutionContext:
        path = self._path(execution_id)
        if not path.exists():
            raise CheckpointNotFound(str(execution_id))
        with self._lock:
            envelope = json.loads(path.read_text())
        if envelope.get("schema_version") != 1:
            raise CheckpointError("Unsupported checkpoint schema version")
        payload = envelope["state"]
        serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        expected = hashlib.sha256(serialized.encode()).hexdigest()
        if envelope.get("state_hash") != expected:
            raise CheckpointError("Checkpoint integrity hash mismatch")
        return ExecutionContext.from_dict(payload)

    def exists(self, execution_id: UUID) -> bool:
        return self._path(execution_id).exists()

    def delete(self, execution_id: UUID) -> None:
        path = self._path(execution_id)
        with self._lock:
            if path.exists():
                path.unlink()

    def list_execution_ids(self) -> list[str]:
        return [path.stem for path in self._root.glob("*.json")]


class SQLiteCheckpointStore:
    """Crash-safe durable checkpoint store using SQLite transactions."""

    def __init__(self, path: str) -> None:
        self._connection = sqlite3.connect(path, check_same_thread=False)
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA synchronous=FULL")
        self._connection.execute(
            """
            CREATE TABLE IF NOT EXISTS execution_checkpoints (
                execution_id TEXT PRIMARY KEY,
                schema_version INTEGER NOT NULL,
                state_json TEXT NOT NULL,
                state_hash TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        self._connection.commit()
        self._lock = RLock()

    def save(self, context: ExecutionContext) -> None:
        context.touch()
        payload = context.to_dict()
        serialized = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        state_hash = hashlib.sha256(serialized.encode()).hexdigest()
        with self._lock:
            self._connection.execute(
                """
                INSERT INTO execution_checkpoints
                    (execution_id, schema_version, state_json, state_hash, updated_at)
                VALUES (?, 1, ?, ?, ?)
                ON CONFLICT(execution_id) DO UPDATE SET
                    schema_version=excluded.schema_version,
                    state_json=excluded.state_json,
                    state_hash=excluded.state_hash,
                    updated_at=excluded.updated_at
                """,
                (
                    str(context.identity.execution_id),
                    serialized,
                    state_hash,
                    context.updated_at.isoformat(),
                ),
            )
            self._connection.commit()

    def load(self, execution_id: UUID) -> ExecutionContext:
        with self._lock:
            row = self._connection.execute(
                "SELECT schema_version, state_json, state_hash FROM execution_checkpoints "
                "WHERE execution_id = ?",
                (str(execution_id),),
            ).fetchone()
        if row is None:
            raise CheckpointNotFound(str(execution_id))
        schema_version, state_json, state_hash = row
        if schema_version != 1:
            raise CheckpointError("Unsupported checkpoint schema version")
        actual_hash = hashlib.sha256(state_json.encode()).hexdigest()
        if actual_hash != state_hash:
            raise CheckpointError("Checkpoint integrity hash mismatch")
        return ExecutionContext.from_dict(json.loads(state_json))

    def delete(self, execution_id: UUID) -> None:
        with self._lock:
            self._connection.execute(
                "DELETE FROM execution_checkpoints WHERE execution_id = ?",
                (str(execution_id),),
            )
            self._connection.commit()

    def exists(self, execution_id: UUID) -> bool:
        with self._lock:
            row = self._connection.execute(
                "SELECT 1 FROM execution_checkpoints WHERE execution_id = ?",
                (str(execution_id),),
            ).fetchone()
        return row is not None

    def close(self) -> None:
        with self._lock:
            self._connection.close()


class CheckpointManager:
    """Coordinates checkpoint persistence for execution lifecycle boundaries."""

    def __init__(self, store: CheckpointStore) -> None:
        self.store = store

    def save(self, context: ExecutionContext) -> None:
        self.store.save(context)

    def load(self, execution_id: UUID) -> ExecutionContext:
        return self.store.load(execution_id)

    def delete(self, execution_id: UUID) -> None:
        self.store.delete(execution_id)
