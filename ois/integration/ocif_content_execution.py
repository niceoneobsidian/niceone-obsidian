"""OIS capability boundary for approved OCIF content execution.

This capability authorizes only the sandbox/no-op execution mode. It deliberately
contains no social-platform publishing adapter.
"""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping
from typing import Any

from ois.integration.spine import OISSpine, SpineRequest
from ois.kernel.contracts import CapabilityContract, InvocationRequest, InvocationResult
from ois.kernel.types import InvocationStatus, RiskLevel, SideEffectLevel
from ois.registries import CapabilityRegistry


class PostgresOCIFApprovalVerifier:
    """Verify the live OCIF approval row and exact current draft in shared PostgreSQL."""

    def __init__(self, connection_factory: Callable[[], Any]) -> None:
        self._connect = connection_factory

    def __call__(self, request: Mapping[str, Any]) -> bool:
        with self._connect() as connection, connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT a.decision, a.draft_id, a.content_sha256, a.draft_version,
                       a.reviewer_id, d.content, d.content_sha256, d.version
                FROM ocif_human_approvals AS a
                JOIN ocif_content_drafts AS d ON d.draft_id = a.draft_id
                WHERE a.approval_id = %s
                """,
                (str(request.get("approval_id", "")),),
            )
            row = cursor.fetchone()
        if row is None:
            return False
        (
            decision,
            draft_id,
            approved_digest,
            approved_version,
            reviewer_id,
            content,
            digest,
            version,
        ) = row
        return (
            decision == "approved"
            and str(draft_id) == str(request.get("draft_id"))
            and str(approved_digest) == str(request.get("content_sha256"))
            and int(approved_version) == int(request.get("draft_version", -1))
            and str(reviewer_id) == str(request.get("reviewer_id"))
            and str(digest) == str(approved_digest)
            and int(version) == int(approved_version)
            and hashlib.sha256(str(content).encode("utf-8")).hexdigest() == str(digest)
        )


class OCIFContentExecutionCapability:
    """Policy-gated execution receipt for a database-verified OCIF approval."""

    def __init__(self, approval_verifier: Callable[[Mapping[str, Any]], bool]) -> None:
        self._approval_verifier = approval_verifier

    contract = CapabilityContract(
        capability_id="ocif.content.execute",
        version="1.0.0",
        description="Authorize a hash-bound approved OCIF draft in sandbox no-op mode.",
        input_schema={
            "type": "object",
            "required": [
                "approval_id",
                "draft_id",
                "content_sha256",
                "draft_version",
                "reviewer_id",
                "idempotency_key",
                "mode",
            ],
        },
        output_schema={"type": "object"},
        risk_level=RiskLevel.MEDIUM,
        permissions=("ocif.content.execute",),
        allowed_domains=("content_workflow",),
        timeout_seconds=15.0,
        max_retries=0,
        side_effects=SideEffectLevel.NONE,
        idempotent=True,
    )

    def invoke(self, request: InvocationRequest) -> InvocationResult:
        payload: Mapping[str, Any] = request.input
        required = (
            "approval_id",
            "draft_id",
            "content_sha256",
            "draft_version",
            "reviewer_id",
            "idempotency_key",
        )
        missing = [key for key in required if not payload.get(key)]
        if missing:
            return InvocationResult(
                invocation_id=request.invocation_id,
                capability_id=self.contract.capability_id,
                status=InvocationStatus.FAILED,
                error={"type": "ValueError", "message": "missing fields: " + ", ".join(missing)},
            )
        if payload.get("mode") != "sandbox_noop":
            return InvocationResult(
                invocation_id=request.invocation_id,
                capability_id=self.contract.capability_id,
                status=InvocationStatus.FAILED,
                error={"type": "PolicyError", "message": "only sandbox_noop mode is supported"},
            )
        try:
            approval_is_current = self._approval_verifier(payload)
        except Exception as exc:
            return InvocationResult(
                invocation_id=request.invocation_id,
                capability_id=self.contract.capability_id,
                status=InvocationStatus.FAILED,
                error={"type": type(exc).__name__, "message": "approval verification failed"},
            )
        if approval_is_current is not True:
            return InvocationResult(
                invocation_id=request.invocation_id,
                capability_id=self.contract.capability_id,
                status=InvocationStatus.FAILED,
                error={
                    "type": "ApprovalVerificationError",
                    "message": "approval is missing, rejected, stale, or not bound to this draft",
                },
            )
        return InvocationResult(
            invocation_id=request.invocation_id,
            capability_id=self.contract.capability_id,
            status=InvocationStatus.SUCCEEDED,
            output={
                "allowed": True,
                "mode": "sandbox_noop",
                "external_side_effects": False,
                "approval_id": str(payload["approval_id"]),
                "draft_id": str(payload["draft_id"]),
                "content_sha256": str(payload["content_sha256"]),
                "draft_version": int(payload["draft_version"]),
                "idempotency_key": str(payload["idempotency_key"]),
            },
            metadata={"authorization_boundary": "ois", "capability_version": "1.0.0"},
        )


def register_ocif_content_execution_capability(
    registry: CapabilityRegistry,
    approval_verifier: Callable[[Mapping[str, Any]], bool],
) -> OCIFContentExecutionCapability:
    """Register the no-op capability with an explicit approval verifier."""
    capability = OCIFContentExecutionCapability(approval_verifier)
    registry.register(capability)
    return capability


def authorize_ocif_content_request(
    spine: OISSpine, request: Mapping[str, Any], *, tenant_id: str
) -> dict[str, Any]:
    """Adapt the OCIF workflow authorization callback to the real OIS spine."""
    idempotency_key = str(request.get("idempotency_key", "")).strip()
    if not idempotency_key:
        return {"allowed": False, "reason": "idempotency_key is required"}
    result = spine.submit(
        SpineRequest(
            objective="Authorize a human-approved OCIF draft in sandbox no-op mode",
            capability_id="ocif.content.execute",
            capability_version="1.0.0",
            tenant_id=tenant_id,
            input=dict(request),
            workflow_id="ocif.content.workflow",
            workflow_version="1.0",
        ),
        invocation_id=idempotency_key,
    )
    if result.status != "succeeded" or not isinstance(result.output, Mapping):
        return {
            "allowed": False,
            "reason": (dict(result.error) if result.error else "OIS did not authorize execution"),
            "ois_execution_id": result.execution_id,
        }
    return {
        **dict(result.output),
        "allowed": result.output.get("allowed") is True,
        "invocation_id": result.invocation_id,
        "ois_execution_id": result.execution_id,
        "authorization_boundary": "ois",
        "capability_version": "1.0.0",
    }
