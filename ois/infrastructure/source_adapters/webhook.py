"""Webhook verification boundary for live source events."""

from __future__ import annotations

import hashlib
import hmac
import json
from typing import Any

from ois.infrastructure.source_gateway import SourceGateway, SourceRequest

from .base import AdapterResult, SourceAdapterRegistry


class WebhookVerifier:
    def __init__(self, *, secret: bytes, algorithm: str = "sha256") -> None:
        if algorithm != "sha256":
            raise ValueError("only sha256 webhook verification is supported")
        self._secret = secret

    def verify(self, payload: bytes, signature: str) -> bool:
        supplied = signature.removeprefix("sha256=")
        expected = hmac.new(
            self._secret, payload, hashlib.sha256
        ).hexdigest()
        return hmac.compare_digest(supplied, expected)

    def ingest(
        self,
        *,
        tenant_id: str,
        workspace_id: str,
        source_id: str,
        record_id: str,
        payload: bytes,
        signature: str,
        gateway: SourceGateway,
    ) -> AdapterResult:
        if not self.verify(payload, signature):
            raise PermissionError("invalid webhook signature")
        decoded: Any = json.loads(payload.decode("utf-8"))
        response = gateway.ingest(
            SourceRequest(
                tenant_id=tenant_id,
                workspace_id=workspace_id,
                source_id=source_id,
                source_record_id=record_id,
                payload=decoded,
                connector_version="webhook-v1",
                schema_version="webhook.event.v1",
            )
        )
        return SourceAdapterRegistry.response(source_id, [response])
