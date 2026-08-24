"""Canonical structural contracts for the OIS next-generation fabrics.

The contracts are intentionally dependency-light. Runtime adapters implement
them behind the existing OIS Kernel, registries, policy and validation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Protocol


class FabricKind(StrEnum):
    WORKFLOW = "workflow"
    DISTRIBUTED_EXECUTION = "distributed_execution"
    LLM_GATEWAY = "llm_gateway"
    EVALUATION = "evaluation"
    AGENT_RUNTIME = "agent_runtime"
    CONTEXT = "context"
    KNOWLEDGE = "knowledge"
    MIDDLEWARE = "middleware"
    REASONING = "reasoning"
    STUDIO = "studio"
    COMPONENT = "component"
    MODEL_RUNTIME = "model_runtime"
    MULTIMODAL = "multimodal"
    SOCIAL = "social"
    LEARNING = "learning"


@dataclass(frozen=True)
class VersionedRef:
    ref_id: str
    version: str = "1.0.0"


@dataclass(frozen=True)
class FabricSpec:
    fabric_id: str
    kind: FabricKind
    version: str = "1.0.0"
    capabilities: tuple[str, ...] = ()
    dependencies: tuple[str, ...] = ()
    policies: tuple[str, ...] = ()


@dataclass(frozen=True)
class WorkflowSpec(VersionedRef):
    triggers: tuple[str, ...] = ()
    nodes: tuple[str, ...] = ()
    edges: tuple[tuple[str, str], ...] = ()
    checkpointable: bool = True
    resumable: bool = True


@dataclass(frozen=True)
class WorkerSpec(VersionedRef):
    queue: str = "default"
    concurrency: int = 1
    max_attempts: int = 3
    heartbeat_seconds: int = 30


@dataclass(frozen=True)
class LLMGatewaySpec(VersionedRef):
    providers: tuple[str, ...] = ()
    routing_policy: str = "capability_first"
    retry_policy: str = "bounded"
    fallback_policy: str = "next_compatible"
    streaming: bool = True
    structured_output: bool = True


@dataclass(frozen=True)
class ModelRoute(VersionedRef):
    provider: str = ""
    model: str = ""
    capabilities: tuple[str, ...] = ()
    cost_profile: dict[str, float] = field(default_factory=dict)
    constraints: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EvaluationSpec(VersionedRef):
    dataset_id: str = ""
    evaluator_ids: tuple[str, ...] = ()
    metrics: tuple[str, ...] = ()
    guardrails: tuple[str, ...] = ()
    promotion_threshold: float = 0.0


@dataclass(frozen=True)
class AgentWorkspace(VersionedRef):
    agent_id: str = ""
    identity_ref: str = ""
    memory_refs: tuple[str, ...] = ()
    skill_refs: tuple[str, ...] = ()
    session_refs: tuple[str, ...] = ()
    policy_refs: tuple[str, ...] = ()


@dataclass(frozen=True)
class ContextRequest(VersionedRef):
    objective: str = ""
    evidence_refs: tuple[str, ...] = ()
    memory_refs: tuple[str, ...] = ()
    knowledge_refs: tuple[str, ...] = ()
    skill_refs: tuple[str, ...] = ()
    token_budget: int | None = None


@dataclass(frozen=True)
class KnowledgeArtifact(VersionedRef):
    source_ref: str = ""
    artifact_type: str = "document"
    content_ref: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    observed_at: str | None = None
    valid_from: str | None = None
    valid_until: str | None = None


@dataclass(frozen=True)
class MiddlewareSpec(VersionedRef):
    stages: tuple[str, ...] = (
        "before_agent",
        "before_model",
        "after_model",
        "before_tool",
        "after_tool",
        "after_agent",
    )
    policies: tuple[str, ...] = ()


@dataclass(frozen=True)
class ReasoningPattern(VersionedRef):
    objective_classes: tuple[str, ...] = ()
    topology: str = ""
    prerequisites: tuple[str, ...] = ()
    failure_modes: tuple[str, ...] = ()
    benchmark_refs: tuple[str, ...] = ()
    cost_profile: dict[str, float] = field(default_factory=dict)


@dataclass(frozen=True)
class StudioArtifact(VersionedRef):
    artifact_type: str = "workflow"
    component_refs: tuple[str, ...] = ()
    graph: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class ComponentSpec(VersionedRef):
    component_type: str = ""
    contract_ref: str = ""
    capability_refs: tuple[str, ...] = ()
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class MultimodalArtifact(VersionedRef):
    media_type: str = ""
    content_ref: str = ""
    transcript_ref: str | None = None
    embedding_ref: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SocialSignal(VersionedRef):
    source_ref: str = ""
    platform: str = ""
    entity_refs: tuple[str, ...] = ()
    topic_refs: tuple[str, ...] = ()
    signal_type: str = ""
    value: float | None = None
    observed_at: str | None = None
    confidence: float = 0.0


@dataclass(frozen=True)
class LearningCandidate(VersionedRef):
    hypothesis: str = ""
    evidence_refs: tuple[str, ...] = ()
    experiment_ref: str | None = None
    affected_refs: tuple[str, ...] = ()
    promotion_state: str = "candidate"
    rollback_ref: str | None = None


class FabricRegistry(Protocol):
    def register(self, spec: FabricSpec) -> None: ...

    def get(self, fabric_id: str) -> FabricSpec | None: ...

    def list(self, kind: FabricKind | None = None) -> tuple[FabricSpec, ...]: ...


@dataclass
class InMemoryFabricRegistry:
    _items: dict[str, FabricSpec] = field(default_factory=dict)

    def register(self, spec: FabricSpec) -> None:
        if spec.fabric_id in self._items:
            raise ValueError(f"fabric already registered: {spec.fabric_id}")
        self._items[spec.fabric_id] = spec

    def get(self, fabric_id: str) -> FabricSpec | None:
        return self._items.get(fabric_id)

    def list(self, kind: FabricKind | None = None) -> tuple[FabricSpec, ...]:
        values = self._items.values()
        if kind is not None:
            values = (item for item in values if item.kind == kind)
        return tuple(sorted(values, key=lambda item: item.fabric_id))
