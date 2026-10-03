"""Replay-resistant webhook security policies."""

from __future__ import annotations

import hashlib
import hmac
import time
from dataclasses import dataclass

from .idempotency import IdempotencyStore


@dataclass(frozen=True)
class WebhookSecurityPolicy:
    secret: bytes
    signature_header: str = "X-Signature"
    timestamp_header: str = "X-Timestamp"
    max_age_seconds: int = 300
    algorithm: str = "sha256"
    prefix: str = "sha256="

    def __post_init__(self) -> None:
        if not self.secret:
            raise ValueError("webhook secret must not be empty")
        if self.algorithm != "sha256":
            raise ValueError("only sha256 webhook signatures are supported")
        if self.max_age_seconds <= 0:
            raise ValueError("max_age_seconds must be positive")


class WebhookSecurity:
    """Verify signed webhook requests before they enter SourceGateway."""

    def __init__(
        self,
        policy: WebhookSecurityPolicy,
        *,
        replay_store: IdempotencyStore | None = None,
        clock: callable = time.time,
    ) -> None:
        self._policy = policy
        self._replay_store = replay_store
        self._clock = clock

    def verify(
        self,
        *,
        payload: bytes,
        signature: str,
        timestamp: str,
        replay_key: str,
        tenant_id: str,
        workspace_id: str,
    ) -> bool:
        try:
            observed = float(timestamp)
        except ValueError:
            return False
        if abs(self._clock() - observed) > self._policy.max_age_seconds:
            return False

        signed = f"{timestamp}.".encode("utf-8") + payload
        digest = hmac.new(self._policy.secret, signed, hashlib.sha256).hexdigest()
        supplied = signature.removeprefix(self._policy.prefix)
        if not hmac.compare_digest(supplied, digest):
            return False

        if self._replay_store is not None and not self._replay_store.claim(
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            key=replay_key,
            event_id=replay_key,
        ):
            return False
        return True
