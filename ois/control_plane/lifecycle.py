"""Canonical OIS Control Plane integration for production lifecycle controls.

Production concerns are adapters around the existing OIS Control Plane and
Kernel. This module deliberately contains no alternate execution runtime.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, cast
from uuid import UUID, uuid4

from ois.kernel.checkpoint import CheckpointStore, InMemoryCheckpointStore
from ois.kernel.contracts import (
    CapabilityContract,
    InvocationRequest,
    InvocationResult,
    PolicyEngine,
)
from ois.kernel.evidence import EvidenceEvent as KernelEvidenceEvent
from ois.kernel.evidence import EvidenceStore as KernelEvidenceStore
from ois.kernel.policy import DefaultPolicyEngine
from ois.kernel.registry import CapabilityEntry as KernelRegistryEntry
from ois.kernel.runtime import ExecutionRuntime
from ois.kernel.state import ExecutionContext, ExecutionIdentity
from ois.kernel.types import InvocationStatus
from ois.registries import CapabilityRegistry
from production.control_plane import (
    RBACABAC,
    AuthorizationPolicy,
    DeploymentAdapter,
    EvidenceLedger,
    InMemoryDeploymentAdapter,
    ProductionControlPlane,
    Subject,
)
from production.evolution import CanaryController, CanaryDecision, LearningLoop, Measurement
from production.semantic_world import SemanticWorld
from production.workers import LeaseQueue, Worker

from .controller import ControlPlane
from .request import ControlRequest


class KernelRegistryAdapter:
    """Adapt the canonical Control Plane registry to the Kernel registry contract."""

    def __init__(self, registry: CapabilityRegistry) -> None:
        self.registry = registry

    def get(self, capability_id: str, version: str) -> KernelRegistryEntry:
        entry = self.registry.resolve(capability_id, version)
        capability = entry.capability
        contract = entry.contract
        if contract is None:
            raise TypeError(f"registered capability has no contract: {capability_id}@{version}")
        return KernelRegistryEntry(
            capability=cast(Any, capability),
            contract=contract,
            id=entry.id,
            version=entry.version,
        )


class KernelEvidenceBridge(KernelEvidenceStore):
    """Forward authoritative Kernel lifecycle events into the shared ledger."""

    def __init__(self, ledger: EvidenceLedger) -> None:
        self.ledger = ledger

    def append(self, event: KernelEvidenceEvent) -> None:
        self.ledger.append(
            str(event.execution_id),
            event.event_type,
            {
                **dict(event.data),
                "kernel_event_id": str(event.event_id),
                "actor": event.actor,
                "component": event.component,
                "timestamp": event.timestamp.isoformat(),
                "correlation_id": event.correlation_id,
                "causation_id": event.causation_id,
            },
        )

    def list(self, execution_id: UUID | None = None) -> tuple[KernelEvidenceEvent, ...]:
        return tuple(self.ledger.list(execution_id))

    def record(
        self,
        execution_id: UUID,
        event_type: str,
        data: Mapping[str, Any] | None = None,
        *,
        actor: str = "kernel",
        component: str = "ois.kernel",
        correlation_id: str | None = None,
        causation_id: str | None = None,
    ) -> KernelEvidenceEvent:
        event = KernelEvidenceEvent(
            execution_id=execution_id,
            event_type=event_type,
            timestamp=datetime.now(UTC),
            event_id=uuid4(),
            actor=actor,
            component=component,
            data=dict(data or {}),
            correlation_id=correlation_id,
            causation_id=causation_id,
        )
        self.append(event)
        return event


class ProductionPolicyAdapter(PolicyEngine):
    """Make production RBAC/ABAC mandatory inside the canonical Kernel policy."""

    def __init__(self, authorization: RBACABAC, fallback: PolicyEngine | None = None) -> None:
        self.authorization = authorization
        self.fallback = fallback or DefaultPolicyEngine()

    def authorize(self, request: InvocationRequest, contract: CapabilityContract) -> bool:
        metadata = request.execution.metadata
        subject = Subject(
            subject_id=str(metadata.get("subject_id", "system")),
            tenant_id=request.execution.identity.tenant_id,
            roles=frozenset(str(role) for role in metadata.get("roles", ())),
            attributes={str(k): str(v) for k, v in dict(metadata.get("attributes", {})).items()},
            permissions=frozenset(str(p) for p in metadata.get("permissions", ())),
        )
        required = contract.permissions[0] if contract.permissions else "execution.invoke"
        self.authorization.authorize(
            subject,
            AuthorizationPolicy(
                permission=required,
                required_attributes={"environment": str(metadata.get("environment", "staging"))},
            ),
        )
        return self.fallback.authorize(request, contract)


@dataclass(frozen=True)
class LifecycleResult:
    result: InvocationResult
    execution_id: str
    evidence_event_ids: tuple[str, ...]
    semantic_entity_id: str
    learning_state: str


@dataclass(frozen=True)
class RolloutResult:
    candidate: str
    decision: CanaryDecision
    state: str
    execution_ids: tuple[str, ...]
    evidence_event_ids: tuple[str, ...]


class OISProductionLifecycle:
    """Bind the canonical Control Plane, Kernel and production lifecycle adapters."""

    def __init__(
        self,
        control_plane: ControlPlane,
        capabilities: CapabilityRegistry,
        *,
        checkpoints: CheckpointStore | None = None,
        policy: PolicyEngine | None = None,
        evidence: EvidenceLedger | None = None,
        world: SemanticWorld | None = None,
        learning: LearningLoop | None = None,
        canary: CanaryController | None = None,
        authorization: RBACABAC | None = None,
        deployment: DeploymentAdapter | None = None,
    ) -> None:
        self.control_plane = control_plane
        self.capabilities = capabilities
        self.evidence = evidence or EvidenceLedger()
        self.world = world or SemanticWorld()
        self.learning = learning or LearningLoop()
        self.canary = canary or CanaryController()
        self.authorization = authorization or RBACABAC()
        self.checkpoints = checkpoints or InMemoryCheckpointStore()
        self.kernel_registry = KernelRegistryAdapter(capabilities)
        self.kernel_evidence = KernelEvidenceBridge(self.evidence)
        self.policy = policy or ProductionPolicyAdapter(self.authorization)
        self.runtime = ExecutionRuntime(
            cast(Any, self.kernel_registry),
            self.checkpoints,
            evidence=self.kernel_evidence,
            policy=self.policy,
        )
        self.deployment = ProductionControlPlane(
            authorization=self.authorization,
            evidence=self.evidence,
            deployment=deployment or InMemoryDeploymentAdapter(),
        )

    def execute(
        self,
        request: ControlRequest,
        *,
        objective: str,
        tenant_id: str = "default",
        invocation_id: str | None = None,
        subject_id: str = "system",
        roles: frozenset[str] = frozenset(),
        permissions: frozenset[str] = frozenset(),
        environment: str = "staging",
        attributes: Mapping[str, str] | None = None,
    ) -> LifecycleResult:
        """Resolve via the existing Control Plane and execute only via the Kernel."""
        self.control_plane.resolve_capability(request)
        context = ExecutionContext(
            identity=ExecutionIdentity(
                tenant_id=tenant_id,
                workflow_id="ois.production.lifecycle",
                workflow_version="1.0.0",
            ),
            objective=objective,
            metadata={
                "subject_id": subject_id,
                "roles": tuple(roles),
                "permissions": tuple(permissions),
                "environment": environment,
                "attributes": dict(attributes or {}),
            },
        )
        execution_id = str(context.identity.execution_id)
        entity = self.world.upsert_entity(
            "execution",
            {"execution_id": execution_id, "objective": objective},
        )
        self.evidence.append(
            execution_id,
            "control_plane.request.accepted",
            {
                "capability_id": request.capability_id,
                "version": request.capability_version,
                "tenant_id": tenant_id,
            },
        )
        self.world.assert_fact(entity.entity_id, "execution.accepted", True, source="control_plane")

        result = self.runtime.execute(
            context,
            request.capability_id,
            request.capability_version,
            dict(request.input),
            invocation_id=invocation_id,
        )
        succeeded = result.status == InvocationStatus.SUCCEEDED
        self.world.assert_fact(
            entity.entity_id,
            "execution.succeeded",
            succeeded,
            source=f"kernel:{result.invocation_id}",
        )
        evaluation = self.learning.evaluate(
            f"capability:{request.capability_id}@{request.capability_version}",
            [Measurement("execution_success", 1.0 if succeeded else 0.0)],
            baseline=0.0,
            minimum_score=0.5,
        )
        learning_state = self.learning.candidate(
            f"capability:{request.capability_id}@{request.capability_version}", evaluation
        )
        if succeeded:
            self.runtime.complete(context)
        return LifecycleResult(
            result=result,
            execution_id=execution_id,
            evidence_event_ids=tuple(
                event.event_id for event in self.evidence.events(execution_id)
            ),
            semantic_entity_id=entity.entity_id,
            learning_state=learning_state,
        )

    def rollout_from_executions(
        self,
        *,
        candidate: str,
        environment: str,
        previous: str,
        executions: Iterable[LifecycleResult],
        traffic_percent: int,
        latency_ms: float,
        release_subject: Subject,
    ) -> RolloutResult:
        """Gate promotion/rollback from actual Kernel execution outcomes."""
        observed = tuple(executions)
        successes = sum(item.result.status is InvocationStatus.SUCCEEDED for item in observed)
        execution_ids = tuple(item.execution_id for item in observed)
        rollout_id = f"rollout:{candidate}:{environment}"
        self.evidence.append(
            rollout_id,
            "rollout.canary.started",
            {
                "candidate": candidate,
                "traffic_percent": traffic_percent,
                "execution_ids": list(execution_ids),
            },
        )
        decision = self.canary.decide(
            candidate,
            traffic_percent,
            successes=successes,
            total=len(observed),
            latency_ms=latency_ms,
        )
        if not decision.passed:
            self.evidence.append(
                rollout_id,
                "rollout.canary.failed",
                {"success_rate": decision.success_rate, "latency_ms": latency_ms},
            )
            rollback = self.deployment.rollback(release_subject, previous, environment)
            self.evidence.append(
                rollout_id,
                "rollout.rollback.verified",
                {"target": previous, "deployment_evidence": list(rollback.evidence_ids)},
            )
            state = "ROLLED_BACK"
        else:
            self.evidence.append(
                rollout_id,
                "rollout.canary.passed",
                {"success_rate": decision.success_rate, "latency_ms": latency_ms},
            )
            activation = self.deployment.activate(
                release_subject, candidate, environment, previous=previous
            )
            self.evidence.append(
                rollout_id,
                "rollout.promoted",
                {"candidate": candidate, "deployment_evidence": list(activation.evidence_ids)},
            )
            state = "PROMOTED"
        return RolloutResult(
            candidate=candidate,
            decision=decision,
            state=state,
            execution_ids=execution_ids,
            evidence_event_ids=tuple(event.event_id for event in self.evidence.events(rollout_id)),
        )

    def worker(self, queue: LeaseQueue, worker_id: str) -> Worker:
        """Create a worker whose handler re-enters the canonical Control Plane."""

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
                subject_id=str(payload.get("subject_id", "worker")),
                roles=frozenset(str(role) for role in payload.get("roles", ())),
                permissions=frozenset(
                    str(permission) for permission in payload.get("permissions", ())
                ),
                environment=str(payload.get("environment", "staging")),
                attributes={str(k): str(v) for k, v in dict(payload.get("attributes", {})).items()},
            )

        return Worker(worker_id, queue, handle)
