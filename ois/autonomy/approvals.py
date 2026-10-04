"""Durable-boundary-ready human approval gates."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from threading import RLock
from uuid import uuid4


class ApprovalDecision(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"


@dataclass(frozen=True)
class ApprovalRequest:
    approval_id: str
    tenant_id: str
    workspace_id: str
    workflow_id: str
    event_id: str
    reason: str
    created_at: datetime
    expires_at: datetime
    decision: ApprovalDecision = ApprovalDecision.PENDING
    decided_by: str | None = None
    decided_at: datetime | None = None


class InMemoryApprovalStore:
    """Reference approval store; production adapters must enforce tenant scope."""

    def __init__(self) -> None:
        self._items: dict[str, ApprovalRequest] = {}
        self._lock = RLock()

    def create(self, request: ApprovalRequest) -> ApprovalRequest:
        with self._lock:
            if request.approval_id in self._items:
                raise ValueError("approval already exists")
            self._items[request.approval_id] = request
            return request

    def get(self, approval_id: str) -> ApprovalRequest | None:
        with self._lock:
            return self._items.get(approval_id)

    def decide(self, approval_id: str, decision: ApprovalDecision, actor: str) -> ApprovalRequest:
        with self._lock:
            current = self._items.get(approval_id)
            if current is None:
                raise KeyError("approval not found")
            if current.decision != ApprovalDecision.PENDING:
                raise ValueError("approval is already decided")
            if datetime.now(UTC) >= current.expires_at:
                expired = ApprovalRequest(**{**current.__dict__, "decision": ApprovalDecision.EXPIRED})
                self._items[approval_id] = expired
                raise ValueError("approval has expired")
            updated = ApprovalRequest(
                **{
                    **current.__dict__,
                    "decision": decision,
                    "decided_by": actor,
                    "decided_at": datetime.now(UTC),
                }
            )
            self._items[approval_id] = updated
            return updated

    def list_pending(self, tenant_id: str, workspace_id: str) -> tuple[ApprovalRequest, ...]:
        with self._lock:
            return tuple(
                item for item in self._items.values()
                if item.tenant_id == tenant_id and item.workspace_id == workspace_id
                and item.decision == ApprovalDecision.PENDING
            )


class ApprovalGate:
    def __init__(self, store: InMemoryApprovalStore, ttl_seconds: int = 3600) -> None:
        if ttl_seconds <= 0:
            raise ValueError("ttl_seconds must be positive")
        self._store = store
        self._ttl_seconds = ttl_seconds

    def request(self, *, tenant_id: str, workspace_id: str, workflow_id: str, event_id: str, reason: str) -> ApprovalRequest:
        now = datetime.now(UTC)
        return self._store.create(
            ApprovalRequest(
                approval_id=str(uuid4()),
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                workflow_id=workflow_id,
                event_id=event_id,
                reason=reason,
                created_at=now,
                expires_at=now.replace(microsecond=0) + timedelta(seconds=self._ttl_seconds),
            )
        )
