"""Dead-letter quarantine and escalation boundary for terminal OIS failures."""

from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import UTC, datetime
from typing import Any, Protocol

from pydantic import BaseModel, Field

from .state import ExecutionContext


class RedisClient(Protocol):
    def lpush(self, name: str, *values: str) -> int: ...

    def publish(self, channel: str, message: str) -> int: ...


class RedisCoordinator(Protocol):
    client: RedisClient


class DLQEscalationPayload(BaseModel):
    """Versioned, integrity-addressable record for a quarantined execution."""

    schema_version: str = "1.0"
    escalation_id: str
    execution_id: str
    tenant_id: str
    objective: str
    fault_type: str
    reason: str
    failed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    frozen_state_snapshot: dict[str, Any]
    payload_sha256: str


class OISDeadLetterInterceptor:
    """Quarantine terminal executions and emit an observable escalation event."""

    def __init__(
        self,
        redis_coordinator: RedisCoordinator,
        *,
        logger: logging.Logger | None = None,
        key_prefix: str = "ois:kernel:dlq",
    ) -> None:
        self.redis = redis_coordinator
        self.logger = logger or logging.getLogger("OIS.Kernel.DLQ")
        self.key_prefix = key_prefix

    @staticmethod
    def _canonical_snapshot(state: ExecutionContext) -> dict[str, Any]:
        return state.to_dict()

    @staticmethod
    def _payload_hash(payload_without_hash: dict[str, Any]) -> str:
        canonical = json.dumps(
            payload_without_hash,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")
        return hashlib.sha256(canonical).hexdigest()

    def intercept_and_quarantine(
        self,
        state: ExecutionContext,
        failure_reason: str,
    ) -> DLQEscalationPayload:
        """Freeze state, enqueue it, publish an event, and return the exact record."""
        snapshot = self._canonical_snapshot(state)
        identity = state.identity
        fault_class = (
            state.last_failure.value if state.last_failure else "CRITICAL_POLICY_VIOLATION"
        )

        base = {
            "schema_version": "1.0",
            "escalation_id": f"ESC-{identity.execution_id}-{time.time_ns()}",
            "execution_id": str(identity.execution_id),
            "tenant_id": identity.tenant_id,
            "objective": state.objective,
            "fault_type": fault_class,
            "reason": failure_reason,
            "failed_at": datetime.now(UTC),
            "frozen_state_snapshot": snapshot,
        }
        payload = DLQEscalationPayload(
            **base,
            payload_sha256=self._payload_hash(base),
        )
        serialized = payload.model_dump_json()
        tenant_key = f"{self.key_prefix}:{identity.tenant_id}"
        self.redis.client.lpush(tenant_key, serialized)
        self.redis.client.publish("ois:events:escalations", serialized)
        self.logger.critical(
            "terminal execution quarantined execution_id=%s fault_type=%s escalation_id=%s",
            payload.execution_id,
            payload.fault_type,
            payload.escalation_id,
        )
        return payload
