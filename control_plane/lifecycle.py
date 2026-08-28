"""Canonical OIS lifecycle bridge for production controls and the Kernel.

This module intentionally lives at the Control Plane boundary. Production
concerns are adapters around the existing Kernel; they do not create a second
execution runtime or authorization path.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from kernel.evidence import EvidenceEvent as KernelEvidenceEvent
from kernel.evidence import EvidenceStore as KernelEvidenceStore
from kernel.runtime import ExecutionRuntime
from kernel.state import ExecutionContext
from ois.kernel.checkpoint import CheckpointStore, InMemoryCheckpointStore
from ois.kernel.contracts import InvocationResult
from ois.kernel.policy import DefaultPolicyEngine, PolicyEngine
from ois.kernel.registry import CapabilityRegistry
from ois.kernel.types import InvocationStatus
from production.control_plane import (
    EvidenceLedger,
    InMemoryDeploymentAdapter,
    ProductionControlPlane,
    Subject,
)
from production.evolution import CanaryController, LearningLoop, Measurement
from production.semantic_world import SemanticWorld
from production.workers import LeaseQueue, Worker

from .controller import ControlPlane
from .request import ControlRequest


class KernelEvidenceBridge(KernelEvidenceStore):
    """Forward authoritative Kernel lifecycle events into the production ledger."""

    def __init__(self, ledger: EvidenceLedger) -> None:
        self.ledger = ledger

    def append(self, event: KernelEvidenceEvent) -> None:
        self.ledger.append(
            str(event.execution_id),
            event.event_type,
            {
                **dict(event.data),
                "event_id": str(event.event_id),
                "actor": event.actor,
                "component": event.component,
                "timestamp": event.timestamp.isoformat(),
                "correlation_id": event.correlation_id,
                "causation_id": event.causation_id,
            },
        )

    def record(self, execution_id: UUID, event_type: str, data: Mapping[str, Any] | None = None, **kwargs: Any) -> KernelEvidenceEvent:
        from datetime import UTC, datetime
        from uuid import uuid4

        event = KernelEvidenceEvent(
            execution_id=execution_id,
            event_type=event_type,
            timestamp=datetime.now(UTC),
            event_id=uuid4(),
            actor=str(kwargs.get("actor", "kernel")),
            component=str(kwargs.get("component", "ois.kernel")),
            data=dict(data or {}),
            correlation_id=kwargs.get("correlation_id"),
            causation_id=kwargs.get("causation_id"),
        )
        self.append(event)
        return event


@dataclass(frozen=True)
class LifecycleResult:
    """Result plus the production evidence and measurement identifiers."""

    result: InvocationResult
    execution_id: str
    evidence_event_ids: tuple[str, ...]
    semantic_entity_id: str
    learning_state: str


class OISProductionLifecycle:
    """Bind Control Plane, Kernel, workers, rollout, world and learning."""

    def __init__(
        self,
        control_plane: ControlPlane,
        registry: CapabilityRegistry,
        *,
        checkpoints: CheckpointStore | None = None,
        policy: PolicyEngine | None = None,
        evidence: EvidenceLedger | None = None,
        world: SemanticWorld | None = None,
        learning: LearningLoop | None = None,
        canary: CanaryController | None = None,
    ) -> None:
        self.control_plane = control_plane
        self.registry = registry
        self.evidence = evidence or EvidenceLedger()
        self.world = world or SemanticWorld()
        self.learning = learning or LearningLoop()
        self.canary = canary or CanaryController()
        self.checkpoints = checkpoints or InMemoryCheckpointStore()
        self.kernel_evidence = KernelEvidenceBridge(self.evidence)
        self.runtime = ExecutionRuntime(
            registry,
            self.checkpoints,
            evidence=self.kernel_evidence,
            policy=policy or DefaultPolicyEngine(),
        )
        self.production = ProductionControlPlane(
            authorization=__import__("production.control_plane", fromlist=["RBACABAC"]).RBACABAC(),
            evidence=self.evidence,
            deployment=InMemoryDeploymentAdapter(),
        )

    def execute(self, request: ControlRequest, *, objective: str, tenant_id: str = "default", invocation_id: str | None = None) -> LifecycleResult:
        """Resolve through Control Plane, then execute only through the Kernel."""
        self.control_plane.resolve_capability(request)
        context = ExecutionContext.create(
            objective=objective,
            tenant_id=tenant_id,
            workflow_id="ois.production.lifecycle",
            workflow_version="1.0.0",
        )
        entity = self.world.upsert_entity("execution", {"execution_id": str(context.identity.execution_id), "objective": objective})
        self.evidence.append(str(context.identity.execution_id), "control_plane.request.accepted", {
            "capability_id": request.capability_id,
            "version": request.capability_version,
            "tenant_id": tenant_id,
        })
        self.world.assert_fact(entity.entity_id, "execution.accepted", True, source="control_plane")

        result = self.runtime.execute(
            context,
            request.capability_id,
            request.capability_version,
            dict(request.input),
            invocation_id=invocation_id,
        )
        status = result.status == InvocationStatus.SUCCEEDED
        self.world.assert_fact(entity.entity_id, "execution.succeeded", status, source=f"kernel:{result.invocation_id}")
        score = 1.0 if status else 0.0
        evaluation = self.learning.evaluate(
            f"capability:{request.capability_id}@{request.capability_version}",
            [Measurement("execution_success", score)],
            baseline=0.0,
            minimum_score=0.5,
        )
        learning_state = self.learning.candidate(
            f"capability:{request.capability_id}@{request.capability_version}",
            evaluation,
        )
        if result.status == InvocationStatus.SUCCEEDED:
            self.runtime.complete(context)
        return LifecycleResult(
            result=result,
            execution_id=str(context.identity.execution_id),
            evidence_event_ids=tuple(event.event_id for event in self.evidence.events(str(context.identity.execution_id))),
            semantic_entity_id=entity.entity_id,
            learning_state=learning_state,
        )

    def worker(self, queue: LeaseQueue, worker_id: str) -> Worker:
        """Create a worker whose handler always crosses the Kernel boundary."""
        def handle(payload: dict[str, Any]) -> LifecycleResult:
            request = ControlRequest(
                capability_id=str(payload["capability_id"]),
                capability_version=str(payload["capability_version"]),
                input=dict(payload.get("input", {})),
            )
            return self.execute(
                request,
                objective=str(payload.get("objective", "worker execution")),
                tenant_id=str(payload.get("tenant_id", "default")),
                invocation_id=payload.get("invocation_id"),
            )

        return Worker(worker_id, queue, handle)
