from __future__ import annotations

from copy import deepcopy
from dataclasses import asdict
from datetime import datetime
from threading import RLock
from typing import Protocol
from uuid import UUID

from .state import ExecutionContext


class CheckpointError(Exception):
    """Base checkpoint error."""


class CheckpointNotFound(CheckpointError):
    """Raised when a checkpoint does not exist."""


class CheckpointStore(Protocol):
    def save(self, context: ExecutionContext) -> None:
        ...

    def load(self, execution_id: UUID) -> ExecutionContext:
        ...

    def delete(self, execution_id: UUID) -> None:
        ...


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
        data = asdict(context)
        return {
            "execution_id": str(context.identity.execution_id),
            "status": context.status.value,
            "created_at": context.created_at.isoformat(),
            "updated_at": context.updated_at.isoformat(),
            "state": data,
        }


class JsonFileCheckpointStore:
    """Durable filesystem-backed checkpoint store."""

    def __init__(self, root_path: str = ".ois/checkpoints") -> None:
        from pathlib import Path

        self._root = Path(root_path)
        self._root.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()

    def _path(self, execution_id: UUID | str):
        return self._root / f"{execution_id}.json"

    def save(self, context: ExecutionContext) -> None:
        import json

        with self._lock:
            payload = asdict(context)
            path = self._path(context.identity.execution_id)
            temporary = path.with_suffix(".tmp")
            temporary.write_text(
                json.dumps(
                    payload,
                    default=lambda value: value.value if hasattr(value, "value") else str(value),
                    indent=2,
                    sort_keys=True,
                )
            )
            temporary.replace(path)

    def load(self, execution_id: UUID) -> ExecutionContext:
        import json

        path = self._path(execution_id)
        if not path.exists():
            raise CheckpointNotFound(str(execution_id))
        with self._lock:
            payload = json.loads(path.read_text())
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
