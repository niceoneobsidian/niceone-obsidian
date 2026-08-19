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
    """
    Reference checkpoint implementation.

    This implementation is intentionally process-local. It establishes the
    persistence contract that a PostgreSQL-backed implementation can satisfy
    later without changing the Kernel API.
    """

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
                raise CheckpointNotFound(
                    f"No checkpoint for execution {execution_id}"
                )

            return deepcopy(context)

    def delete(self, execution_id: UUID) -> None:
        with self._lock:
            self._store.pop(execution_id, None)

    def exists(self, execution_id: UUID) -> bool:
        with self._lock:
            return execution_id in self._store

    def snapshot(self, execution_id: UUID) -> dict:
        context = self.load(execution_id)

        data = asdict(context)

        return {
            "execution_id": str(
                context.identity.execution_id
            ),
            "status": context.status.value,
            "created_at": context.created_at.isoformat(),
            "updated_at": context.updated_at.isoformat(),
            "state": data,
        }


class JsonFileCheckpointStore:
    """
    Durable filesystem-backed checkpoint store.

    Stores serialized ExecutionContext snapshots as JSON files keyed
    by execution_id.

    This is the kernel reference durable implementation. It deliberately
    remains infrastructure-neutral so a PostgreSQL adapter can replace
    it later without changing runtime/orchestrator contracts.
    """

    def __init__(self, root_path: str = ".ois/checkpoints") -> None:
        from pathlib import Path
        from threading import RLock

        self._root = Path(root_path)
        self._root.mkdir(parents=True, exist_ok=True)
        self._lock = RLock()

    def _path(self, execution_id: str):
        return self._root / f"{execution_id}.json"

    def save(self, context) -> None:
        import json
        from dataclasses import asdict, is_dataclass

        with self._lock:
            payload = (
                asdict(context)
                if is_dataclass(context)
                else context.model_dump()
                if hasattr(context, "model_dump")
                else context.dict()
                if hasattr(context, "dict")
                else vars(context)
            )

            path = self._path(context.identity.execution_id)
            temporary = path.with_suffix(".tmp")

            temporary.write_text(
                json.dumps(
                    payload,
                    default=lambda value: (
                        value.value
                        if hasattr(value, "value")
                        else str(value)
                    ),
                    indent=2,
                    sort_keys=True,
                )
            )

            temporary.replace(path)

    def load(self, execution_id: str):
        import json

        from .state import ExecutionContext

        path = self._path(execution_id)

        if not path.exists():
            raise CheckpointNotFound(execution_id)

        with self._lock:
            payload = json.loads(path.read_text())

        return ExecutionContext.from_dict(payload)

    def exists(self, execution_id: str) -> bool:
        return self._path(execution_id).exists()
