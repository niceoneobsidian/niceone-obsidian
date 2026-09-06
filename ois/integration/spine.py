"""End-to-end OIS spine joining intent, policy, Kernel execution and evidence.

This module is deliberately an integration layer, not a replacement Kernel.
Natural-language intent is normalized into a deterministic structured request;
the existing Kernel remains authoritative for validation, authorization,
execution, checkpointing, idempotency and evidence.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any
from uuid import uuid4

from ois.kernel.checkpoint import CheckpointStore, InMemoryCheckpointStore
from ois.kernel.evidence import EvidenceLedger, EvidenceStore
from ois.kernel.policy import AuthorizationDenied, DefaultPolicyEngine, PolicyEngine
from ois.kernel.runtime import ExecutionRuntime
from ois.kernel.state import ExecutionContext, ExecutionIdentity
from ois.kernel.types import ExecutionStatus
from ois.registries import CapabilityRegistry


@dataclass(frozen=True)
class SpineRequest:
    """Governed request entering the OIS spine."""

    objective: str
    capability_id: str
    capability_version: str
    input: Mapping[str, Any] = field(default_factory=dict)
    tenant_id: str = "default"
    workflow_id: str = "ois.spine"
    workflow_version: str = "1.0"


@dataclass(frozen=True)
class SpineResult:
    """Observable result of one governed spine execution."""

    execution_id: str
    invocation_id: str
    status: str
    output: Any = None
    error: Mapping[str, Any] | None = None
    evidence: tuple[Mapping[str, Any], ...] = ()


class OISSpine:
    """Coordinate the canonical OIS lifecycle around the verified Kernel."""

    def __init__(
        self,
        registry: CapabilityRegistry,
        *,
        checkpoint_store: CheckpointStore | None = None,
        evidence: EvidenceStore | None = None,
        policy: PolicyEngine | None = None,
    ) -> None:
        self.registry = registry
        self.evidence = evidence or EvidenceLedger()
        self.checkpoints = checkpoint_store or InMemoryCheckpointStore()
        self.policy = policy or DefaultPolicyEngine()
        self.runtime = ExecutionRuntime(
            registry,
            self.checkpoints,
            evidence=self.evidence,
            policy=self.policy,
        )

    def submit(self, request: SpineRequest, *, invocation_id: str | None = None) -> SpineResult:
        """Run THINK → VERIFY → AUTHORIZE → ACT → VALIDATE → EVIDENCE."""
        execution_id = str(uuid4())
        context = ExecutionContext(
            identity=ExecutionIdentity(
                tenant_id=request.tenant_id,
                workflow_id=request.workflow_id,
                workflow_version=request.workflow_version,
            ),
            objective=request.objective,
            metadata={"integration": "ois.spine", "schema_version": 1},
        )
        execution_id = str(context.identity.execution_id)
        context.intent = {
            "objective": request.objective,
            "capability_id": request.capability_id,
            "capability_version": request.capability_version,
        }
        context.plan = {
            "type": "single_capability",
            "nodes": [request.capability_id],
        }
        self.evidence.record(execution_id, "spine.intent.accepted", context.intent)
        self.checkpoints.save(context)

        try:
            result = self.runtime.execute(
                context,
                request.capability_id,
                request.capability_version,
                dict(request.input),
                invocation_id=invocation_id,
            )
        except AuthorizationDenied as exc:
            context.error = {"type": type(exc).__name__, "message": str(exc)}
            context.set_status(ExecutionStatus.STOPPED)
            self.evidence.record(
                execution_id,
                "spine.authorization.denied",
                {"capability_id": request.capability_id, "reason": str(exc)},
            )
            self.checkpoints.save(context)
            return SpineResult(
                execution_id=execution_id,
                invocation_id=invocation_id or "",
                status="denied",
                error={"type": type(exc).__name__, "message": str(exc)},
                evidence=tuple(self.evidence.events(execution_id)),
            )

        if result.status.value == "succeeded":
            self.runtime.complete(context)
        self.evidence.record(
            execution_id,
            "spine.verified",
            {"status": result.status.value, "capability_id": request.capability_id},
        )
        return SpineResult(
            execution_id=execution_id,
            invocation_id=result.invocation_id,
            status=result.status.value,
            output=result.output,
            error=result.error,
            evidence=tuple(self.evidence.events(execution_id)),
        )
