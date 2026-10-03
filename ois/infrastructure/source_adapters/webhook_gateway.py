"""HTTP-facing webhook ingestion boundary."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from ois.infrastructure.source_adapters.base import AdapterResult
from ois.infrastructure.source_gateway import SourceGateway, WebhookSecurity
from ois.infrastructure.source_gateway.gateway import SourceRequest


@dataclass(frozen=True)
class WebhookRequest:
    tenant_id: str
    workspace_id: str
    source_id: str
    record_id: str
    body: bytes
    signature: str
    timestamp: str
    idempotency_key: str

    def __post_init__(self) -> None:
        if not self.tenant_id or not self.workspace_id or not self.source_id:
            raise ValueError("webhook tenant, workspace, and source are required")
        if not self.record_id or not self.idempotency_key:
            raise ValueError("webhook record and idempotency keys are required")


class WebhookGateway:
    """Validate, parse, deduplicate, and route inbound webhooks."""

    def __init__(
        self,
        *,
        gateway: SourceGateway,
        security: WebhookSecurity,
        max_body_bytes: int = 1_048_576,
    ) -> None:
        if max_body_bytes <= 0:
            raise ValueError("max_body_bytes must be positive")
        self._gateway = gateway
        self._security = security
        self._max_body_bytes = max_body_bytes

    def receive(self, request: WebhookRequest) -> AdapterResult:
        if len(request.body) > self._max_body_bytes:
            raise ValueError("webhook payload exceeds configured size limit")
        if not self._security.verify(
            payload=request.body,
            signature=request.signature,
            timestamp=request.timestamp,
            replay_key=request.idempotency_key,
            tenant_id=request.tenant_id,
            workspace_id=request.workspace_id,
        ):
            raise PermissionError("invalid or replayed webhook")

        try:
            payload = json.loads(request.body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("webhook payload must be valid JSON") from exc
        if not isinstance(payload, dict):
            raise ValueError("webhook payload must be a JSON object")

        response = self._gateway.ingest(
            SourceRequest(
                tenant_id=request.tenant_id,
                workspace_id=request.workspace_id,
                source_id=request.source_id,
                source_record_id=request.record_id,
                payload=payload,
                connector_version="webhook-v2",
                schema_version="source.event.v1",
                idempotency_key=request.idempotency_key,
                event_type=str(payload.get("type", "source.webhook")),
            )
        )
        return AdapterResult(
            source_id=request.source_id,
            records=1 if response.accepted else 0,
            evidence_ids=(response.evidence_id,) if response.accepted else (),
            event_ids=(response.event_id,) if response.accepted else (),
            payload_hashes=(response.payload_hash,) if response.accepted else (),
        )
