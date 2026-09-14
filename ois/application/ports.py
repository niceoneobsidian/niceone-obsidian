"""Infrastructure-independent ports used by application services."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from ois.contracts import AuthorizationDecision, EvidenceRecord, ExecutionRequest


class AuthorizationPort(Protocol):
    def authorize(self, request: ExecutionRequest) -> AuthorizationDecision: ...


class EvidenceRepository(Protocol):
    """Durable evidence boundary; adapters own transactions and storage details."""

    def append(self, record: EvidenceRecord) -> None: ...

    def list_for_execution(self, execution_id: UUID) -> Sequence[EvidenceRecord]: ...


class ExecutionStateRepository(Protocol):
    def load_state(self, execution_id: UUID) -> str | None: ...

    def save_state(self, execution_id: UUID, state: str) -> None: ...


class SideEffectExecutor(Protocol):
    def execute(self, request: ExecutionRequest) -> object: ...
