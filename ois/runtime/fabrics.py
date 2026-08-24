"""Runtime bindings for the OIS structural fabrics.

Reference providers are intentionally in-memory. All externally visible
capabilities remain behind the existing OIS Kernel contracts.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from threading import RLock
from typing import Any, Callable

from ois.architecture.fabrics import (
    AgentWorkspace,
    ComponentSpec,
    ContextRequest,
    KnowledgeArtifact,
    LearningCandidate,
    LLMGatewaySpec,
    MiddlewareSpec,
    ModelRoute,
    MultimodalArtifact,
    ReasoningPattern,
    SocialSignal,
    StudioArtifact,
    WorkerSpec,
    WorkflowSpec,
)
from ois.kernel.contracts import (
    AgentContract,
    CapabilityContract,
    InvocationRequest,
    InvocationResult,
)
from ois.kernel.registry import CapabilityRegistry
from ois.kernel.types import InvocationStatus, RiskLevel, SideEffectLevel

CAPABILITY_VERSION = "1.0.0"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class InMemoryWorkflowEngine:
    specs: dict[str, WorkflowSpec] = field(default_factory=dict)
    state: dict[str, dict[str, Any]] = field(default_factory=dict)

    def register(self, spec: WorkflowSpec) -> None:
        if spec.ref_id in self.specs:
            raise ValueError(f"workflow already registered: {spec.ref_id}")
        self._validate(spec)
        self.specs[spec.ref_id] = spec

    def start(
        self,
        workflow_id: str,
        execution_id: str,
        inputs: dict[str, Any],
    ) -> dict[str, Any]:
        if workflow_id not in self.specs:
            raise LookupError(f"workflow not found: {workflow_id}")
        record: dict[str, Any] = {
            "workflow_id": workflow_id,
            "execution_id": execution_id,
            "status": "ready",
            "completed_nodes": [],
            "inputs": dict(inputs),
            "outputs": {},
            "checkpointed_at": None,
        }
        self.state[execution_id] = record
        return dict(record)

    def checkpoint(self, execution_id: str, node_id: str, output: Any) -> None:
        record = self.state[execution_id]
        if node_id not in record["completed_nodes"]:
            record["completed_nodes"].append(node_id)
        record["outputs"][node_id] = output
        record["checkpointed_at"] = _now()
        record["status"] = "running"

    def resume(self, execution_id: str) -> dict[str, Any]:
        return dict(self.state[execution_id])

    @staticmethod
    def _validate(spec: WorkflowSpec) -> None:
        nodes = set(spec.nodes)
        if len(nodes) != len(spec.nodes):
            raise ValueError("workflow contains duplicate nodes")
        if any(a not in nodes or b not in nodes for a, b in spec.edges):
            raise ValueError("workflow edge references an unknown node")


@dataclass
class InMemoryWorkerFabric:
    queues: dict[str, deque[dict[str, Any]]] = field(
        default_factory=lambda: defaultdict(deque)
    )
    workers: dict[str, WorkerSpec] = field(default_factory=dict)
    attempts: dict[str, int] = field(default_factory=dict)
    results: dict[str, Any] = field(default_factory=dict)
    _lock: RLock = field(default_factory=RLock)

    def register_worker(self, spec: WorkerSpec) -> None:
        if spec.ref_id in self.workers:
            raise ValueError(f"worker already registered: {spec.ref_id}")
        if spec.concurrency < 1 or spec.max_attempts < 1:
            raise ValueError("worker concurrency and max_attempts must be positive")
        self.workers[spec.ref_id] = spec

    def submit(self, job_id: str, queue: str, payload: dict[str, Any]) -> None:
        with self._lock:
            self.queues[queue].append(
                {"job_id": job_id, "payload": dict(payload)}
            )
            self.attempts.setdefault(job_id, 0)

    def claim(self, queue: str) -> dict[str, Any] | None:
        with self._lock:
            if not self.queues[queue]:
                return None
            return self.queues[queue].popleft()

    def complete(self, job_id: str, result: Any) -> None:
        with self._lock:
            self.results[job_id] = result

    def retry(self, worker_id: str, job: dict[str, Any]) -> bool:
        worker = self.workers[worker_id]
        job_id = job["job_id"]
        self.attempts[job_id] += 1
        if self.attempts[job_id] >= worker.max_attempts:
            return False
        self.queues[worker.queue].append(job)
        return True


@dataclass
class InMemoryModelRouter:
    routes: list[ModelRoute] = field(default_factory=list)

    def register(self, route: ModelRoute) -> None:
        self.routes.append(route)
        self.routes.sort(
            key=lambda item: (item.provider, item.model, item.version)
        )

    def select(
        self,
        required: set[str],
        constraints: dict[str, Any] | None = None,
    ) -> ModelRoute:
        constraints = constraints or {}
        candidates = [
            route
            for route in self.routes
            if required.issubset(route.capabilities)
            and all(
                route.constraints.get(key) == value
                for key, value in constraints.items()
            )
        ]
        if not candidates:
            raise LookupError(
                f"no model route satisfies capabilities={sorted(required)}"
            )
        return min(candidates, key=lambda route: sum(route.cost_profile.values()))


@dataclass
class InMemoryLLMGateway:
    spec: LLMGatewaySpec
    router: InMemoryModelRouter
    providers: dict[str, Callable[[str, dict[str, Any]], Any]] = field(
        default_factory=dict
    )
    telemetry: list[dict[str, Any]] = field(default_factory=list)

    def register_provider(
        self,
        provider_id: str,
        invoke: Callable[[str, dict[str, Any]], Any],
    ) -> None:
        self.providers[provider_id] = invoke

    def invoke(
        self,
        prompt: str,
        *,
        capabilities: set[str] | None = None,
        options: dict[str, Any] | None = None,
    ) -> Any:
        options = options or {}
        required = capabilities or set()
        route = self.router.select(required, options.get("constraints"))
        provider = self.providers.get(route.provider)
        if provider is None:
            raise LookupError(f"provider not registered: {route.provider}")

        try:
            result = provider(route.model, {"prompt": prompt, **options})
        except Exception as exc:
            self.telemetry.append(
                {
                    "provider": route.provider,
                    "model": route.model,
                    "status": "failed",
                    "error": type(exc).__name__,
                }
            )
            if self.spec.fallback_policy != "next_compatible":
                raise
            for fallback in self.router.routes:
                if fallback == route or not required.issubset(fallback.capabilities):
                    continue
                fallback_provider = self.providers.get(fallback.provider)
                if fallback_provider is not None:
                    return fallback_provider(
                        fallback.model,
                        {"prompt": prompt, **options},
                    )
            raise
        else:
            self.telemetry.append(
                {
                    "provider": route.provider,
                    "model": route.model,
                    "started_at": _now(),
                    "status": "succeeded",
                }
            )
            return result


@dataclass
class InMemoryAgentRuntime:
    workspaces: dict[str, AgentWorkspace] = field(default_factory=dict)
    sessions: dict[str, dict[str, Any]] = field(default_factory=dict)

    def register(self, workspace: AgentWorkspace) -> None:
        if workspace.agent_id in self.workspaces:
            raise ValueError(
                f"agent workspace already registered: {workspace.agent_id}"
            )
        self.workspaces[workspace.agent_id] = workspace

    def open_session(self, agent_id: str, session_id: str) -> dict[str, Any]:
        if agent_id not in self.workspaces:
            raise LookupError(f"agent workspace not found: {agent_id}")
        record: dict[str, Any] = {
            "session_id": session_id,
            "agent_id": agent_id,
            "messages": [],
            "working_memory": {},
            "status": "active",
        }
        self.sessions[session_id] = record
        return dict(record)

    def append(self, session_id: str, role: str, content: Any) -> None:
        self.sessions[session_id]["messages"].append(
            {"role": role, "content": content}
        )

    def close(self, session_id: str) -> None:
        self.sessions[session_id]["status"] = "closed"


@dataclass
class InMemoryContextEngine:
    evidence: dict[str, Any] = field(default_factory=dict)
    memory: dict[str, Any] = field(default_factory=dict)
    knowledge: dict[str, Any] = field(default_factory=dict)
    skills: dict[str, Any] = field(default_factory=dict)

    def assemble(self, request: ContextRequest) -> dict[str, Any]:
        context: dict[str, Any] = {
            "objective": request.objective,
            "evidence": [
                self.evidence[ref]
                for ref in request.evidence_refs
                if ref in self.evidence
            ],
            "memory": [
                self.memory[ref]
                for ref in request.memory_refs
                if ref in self.memory
            ],
            "knowledge": [
                self.knowledge[ref]
                for ref in request.knowledge_refs
                if ref in self.knowledge
            ],
            "skills": [
                self.skills[ref]
                for ref in request.skill_refs
                if ref in self.skills
            ],
        }
        if request.token_budget is not None:
            context["token_budget"] = request.token_budget
        return context


@dataclass
class InMemoryKnowledgeEngine:
    artifacts: dict[str, KnowledgeArtifact] = field(default_factory=dict)

    def ingest(self, artifact: KnowledgeArtifact) -> None:
        self.artifacts[artifact.ref_id] = artifact

    def retrieve(
        self,
        query: str,
        *,
        artifact_type: str | None = None,
    ) -> tuple[KnowledgeArtifact, ...]:
        terms = {term.lower() for term in query.split() if term}
        scored: list[tuple[int, KnowledgeArtifact]] = []
        for artifact in self.artifacts.values():
            if artifact_type and artifact.artifact_type != artifact_type:
                continue
            haystack = " ".join(
                (artifact.source_ref, artifact.content_ref, str(artifact.metadata))
            ).lower()
            score = sum(term in haystack for term in terms)
            if score:
                scored.append((score, artifact))
        scored.sort(key=lambda pair: (-pair[0], pair[1].ref_id))
        return tuple(artifact for _, artifact in scored)


@dataclass
class InMemoryMiddleware:
    spec: MiddlewareSpec
    hooks: dict[str, list[Callable[[dict[str, Any]], dict[str, Any]]]] = field(
        default_factory=lambda: defaultdict(list)
    )

    def add(
        self,
        stage: str,
        hook: Callable[[dict[str, Any]], dict[str, Any]],
    ) -> None:
        if stage not in self.spec.stages:
            raise ValueError(f"unsupported middleware stage: {stage}")
        self.hooks[stage].append(hook)

    def run(self, stage: str, state: dict[str, Any]) -> dict[str, Any]:
        current = dict(state)
        for hook in self.hooks[stage]:
            current = hook(current)
        return current


@dataclass
class InMemoryReasoningRegistry:
    patterns: dict[str, ReasoningPattern] = field(default_factory=dict)

    def register(self, pattern: ReasoningPattern) -> None:
        if pattern.ref_id in self.patterns:
            raise ValueError(f"reasoning pattern already registered: {pattern.ref_id}")
        self.patterns[pattern.ref_id] = pattern

    def select(
        self,
        objective_class: str,
        available: set[str] | None = None,
    ) -> ReasoningPattern:
        available = available or set()
        candidates = [
            pattern
            for pattern in self.patterns.values()
            if objective_class in pattern.objective_classes
            and set(pattern.prerequisites).issubset(available)
        ]
        if not candidates:
            raise LookupError(
                f"no reasoning pattern for objective={objective_class}"
            )
        return min(
            candidates,
            key=lambda pattern: (
                sum(pattern.cost_profile.values()),
                pattern.ref_id,
            ),
        )


@dataclass
class InMemoryStudio:
    artifacts: dict[str, StudioArtifact] = field(default_factory=dict)

    def save(self, artifact: StudioArtifact) -> None:
        self.artifacts[artifact.ref_id] = artifact

    def validate(self, artifact_id: str) -> None:
        artifact = self.artifacts[artifact_id]
        components = set(artifact.component_refs)
        if any(
            source not in components or target not in components
            for source, target in artifact.graph
        ):
            raise ValueError("studio graph references unknown components")


@dataclass
class InMemoryComponentRegistry:
    components: dict[str, ComponentSpec] = field(default_factory=dict)

    def register(self, component: ComponentSpec) -> None:
        if component.ref_id in self.components:
            raise ValueError(f"component already registered: {component.ref_id}")
        self.components[component.ref_id] = component


@dataclass
class InMemoryMultimodalEngine:
    artifacts: dict[str, MultimodalArtifact] = field(default_factory=dict)

    def register(self, artifact: MultimodalArtifact) -> None:
        self.artifacts[artifact.ref_id] = artifact

    def inspect(self, artifact_id: str) -> dict[str, Any]:
        artifact = self.artifacts[artifact_id]
        return {
            "ref_id": artifact.ref_id,
            "media_type": artifact.media_type,
            "content_ref": artifact.content_ref,
            "transcript_ref": artifact.transcript_ref,
            "embedding_ref": artifact.embedding_ref,
            "metadata": dict(artifact.metadata),
        }


@dataclass
class InMemorySocialFabric:
    signals: list[SocialSignal] = field(default_factory=list)

    def ingest(self, signal: SocialSignal) -> None:
        if not 0.0 <= signal.confidence <= 1.0:
            raise ValueError("social signal confidence must be between 0 and 1")
        self.signals.append(signal)

    def query(
        self,
        *,
        platform: str | None = None,
        topic: str | None = None,
    ) -> tuple[SocialSignal, ...]:
        return tuple(
            signal
            for signal in self.signals
            if (platform is None or signal.platform == platform)
            and (topic is None or topic in signal.topic_refs)
        )


@dataclass
class InMemoryLearningFabric:
    candidates: dict[str, LearningCandidate] = field(default_factory=dict)

    def propose(self, candidate: LearningCandidate) -> None:
        if candidate.promotion_state != "candidate":
            raise ValueError("new learning proposals must enter as candidate")
        self.candidates[candidate.ref_id] = candidate

    def promote(
        self,
        ref_id: str,
        *,
        approved: bool,
        evidence_refs: tuple[str, ...] = (),
    ) -> LearningCandidate:
        current = self.candidates[ref_id]
        if not approved or not evidence_refs:
            raise PermissionError(
                "promotion requires explicit approval and evaluation evidence"
            )
        promoted = LearningCandidate(
            ref_id=current.ref_id,
            version=current.version,
            hypothesis=current.hypothesis,
            evidence_refs=current.evidence_refs + evidence_refs,
            experiment_ref=current.experiment_ref,
            affected_refs=current.affected_refs,
            promotion_state="approved",
            rollback_ref=current.rollback_ref,
        )
        self.candidates[ref_id] = promoted
        return promoted


@dataclass
class FabricRuntime:
    workflow: InMemoryWorkflowEngine = field(default_factory=InMemoryWorkflowEngine)
    workers: InMemoryWorkerFabric = field(default_factory=InMemoryWorkerFabric)
    model_router: InMemoryModelRouter = field(default_factory=InMemoryModelRouter)
    llm_gateway: InMemoryLLMGateway | None = None
    agents: InMemoryAgentRuntime = field(default_factory=InMemoryAgentRuntime)
    context: InMemoryContextEngine = field(default_factory=InMemoryContextEngine)
    knowledge: InMemoryKnowledgeEngine = field(default_factory=InMemoryKnowledgeEngine)
    middleware: InMemoryMiddleware = field(
        default_factory=lambda: InMemoryMiddleware(
            MiddlewareSpec("ois.middleware")
        )
    )
    reasoning: InMemoryReasoningRegistry = field(
        default_factory=InMemoryReasoningRegistry
    )
    studio: InMemoryStudio = field(default_factory=InMemoryStudio)
    components: InMemoryComponentRegistry = field(
        default_factory=InMemoryComponentRegistry
    )
    multimodal: InMemoryMultimodalEngine = field(
        default_factory=InMemoryMultimodalEngine
    )
    social: InMemorySocialFabric = field(default_factory=InMemorySocialFabric)
    learning: InMemoryLearningFabric = field(default_factory=InMemoryLearningFabric)

    def configure_gateway(self, spec: LLMGatewaySpec) -> InMemoryLLMGateway:
        self.llm_gateway = InMemoryLLMGateway(spec, self.model_router)
        return self.llm_gateway

    def bind_workflow(self, spec: WorkflowSpec) -> None:
        self.workflow.register(spec)

    def bind_worker(self, spec: WorkerSpec) -> None:
        self.workers.register_worker(spec)

    def bind_agent(self, workspace: AgentWorkspace) -> None:
        self.agents.register(workspace)

    def bind_context(self, request: ContextRequest) -> dict[str, Any]:
        return self.context.assemble(request)

    def bind_knowledge(self, artifact: KnowledgeArtifact) -> None:
        self.knowledge.ingest(artifact)

    def bind_reasoning(self, pattern: ReasoningPattern) -> None:
        self.reasoning.register(pattern)

    def bind_component(self, component: ComponentSpec) -> None:
        self.components.register(component)

    def bind_studio(self, artifact: StudioArtifact) -> None:
        self.studio.save(artifact)
        self.studio.validate(artifact.ref_id)

    def bind_multimodal(self, artifact: MultimodalArtifact) -> None:
        self.multimodal.register(artifact)

    def bind_social(self, signal: SocialSignal) -> None:
        self.social.ingest(signal)

    def bind_learning(self, candidate: LearningCandidate) -> None:
        self.learning.propose(candidate)


@dataclass
class FabricCapability:
    capability_id: str
    handler: Callable[[dict[str, Any]], Any]
    contract: CapabilityContract

    def invoke(self, request: InvocationRequest) -> InvocationResult:
        try:
            output = self.handler(dict(request.input))
        except Exception as exc:
            return InvocationResult(
                invocation_id=request.invocation_id,
                capability_id=self.contract.capability_id,
                status=InvocationStatus.FAILED,
                error={"type": type(exc).__name__, "message": str(exc)},
                completed_at=_now(),
            )
        return InvocationResult(
            invocation_id=request.invocation_id,
            capability_id=self.contract.capability_id,
            status=InvocationStatus.SUCCEEDED,
            output=output,
            completed_at=_now(),
        )


def _contract(
    capability_id: str,
    description: str,
    *,
    agent: bool = False,
) -> CapabilityContract:
    if agent:
        return AgentContract(
            capability_id=capability_id,
            version=CAPABILITY_VERSION,
            description=description,
            risk_level=RiskLevel.LOW,
            timeout_seconds=60.0,
            max_retries=0,
            side_effects=SideEffectLevel.NONE,
            idempotent=True,
            max_iterations=4,
        )
    return CapabilityContract(
        capability_id=capability_id,
        version=CAPABILITY_VERSION,
        description=description,
        risk_level=RiskLevel.LOW,
        timeout_seconds=60.0,
        max_retries=0,
        side_effects=SideEffectLevel.NONE,
        idempotent=True,
    )


def register_fabric_capabilities(
    registry: CapabilityRegistry,
    runtime: FabricRuntime,
) -> tuple[str, ...]:
    """Expose fabric operations through the existing Kernel registry."""

    def workflow_handler(inputs: dict[str, Any]) -> dict[str, Any]:
        return runtime.workflow.start(
            inputs["workflow_id"],
            inputs["execution_id"],
            inputs.get("inputs", {}),
        )

    def worker_handler(inputs: dict[str, Any]) -> dict[str, Any]:
        runtime.workers.submit(
            inputs["job_id"],
            inputs.get("queue", "default"),
            inputs.get("payload", {}),
        )
        return {"job_id": inputs["job_id"], "status": "queued"}

    def llm_handler(inputs: dict[str, Any]) -> Any:
        if runtime.llm_gateway is None:
            raise LookupError("LLM gateway is not configured")
        return runtime.llm_gateway.invoke(
            inputs["prompt"],
            capabilities=set(inputs.get("capabilities", [])),
            options=inputs.get("options", {}),
        )

    def agent_handler(inputs: dict[str, Any]) -> dict[str, Any]:
        return runtime.agents.open_session(
            inputs["agent_id"],
            inputs["session_id"],
        )

    def context_handler(inputs: dict[str, Any]) -> dict[str, Any]:
        request = ContextRequest(
            ref_id=inputs.get("request_id", "context"),
            objective=inputs.get("objective", ""),
            evidence_refs=tuple(inputs.get("evidence_refs", ())),
            memory_refs=tuple(inputs.get("memory_refs", ())),
            knowledge_refs=tuple(inputs.get("knowledge_refs", ())),
            skill_refs=tuple(inputs.get("skill_refs", ())),
            token_budget=inputs.get("token_budget"),
        )
        return runtime.bind_context(request)

    def knowledge_handler(inputs: dict[str, Any]) -> list[dict[str, Any]]:
        artifacts = runtime.knowledge.retrieve(
            inputs.get("query", ""),
            artifact_type=inputs.get("artifact_type"),
        )
        return [artifact.__dict__ for artifact in artifacts]

    def reasoning_handler(inputs: dict[str, Any]) -> dict[str, Any]:
        pattern = runtime.reasoning.select(
            inputs["objective_class"],
            set(inputs.get("available", [])),
        )
        return pattern.__dict__

    def multimodal_handler(inputs: dict[str, Any]) -> dict[str, Any]:
        return runtime.multimodal.inspect(inputs["artifact_id"])

    def social_handler(inputs: dict[str, Any]) -> list[dict[str, Any]]:
        signals = runtime.social.query(
            platform=inputs.get("platform"),
            topic=inputs.get("topic"),
        )
        return [signal.__dict__ for signal in signals]

    def learning_handler(inputs: dict[str, Any]) -> dict[str, str]:
        candidate = LearningCandidate(
            ref_id=inputs["ref_id"],
            hypothesis=inputs["hypothesis"],
            evidence_refs=tuple(inputs.get("evidence_refs", ())),
            experiment_ref=inputs.get("experiment_ref"),
            affected_refs=tuple(inputs.get("affected_refs", ())),
        )
        runtime.bind_learning(candidate)
        return {"ref_id": candidate.ref_id, "status": "candidate"}

    bindings: tuple[tuple[str, Callable[[dict[str, Any]], Any], bool], ...] = (
        ("fabric.workflow", workflow_handler, False),
        ("fabric.worker.submit", worker_handler, False),
        ("fabric.llm.invoke", llm_handler, False),
        ("fabric.agent.session", agent_handler, True),
        ("fabric.context.assemble", context_handler, False),
        ("fabric.knowledge.retrieve", knowledge_handler, False),
        ("fabric.reasoning.select", reasoning_handler, False),
        ("fabric.multimodal.inspect", multimodal_handler, False),
        ("fabric.social.query", social_handler, False),
        ("fabric.learning.propose", learning_handler, False),
    )

    registered: list[str] = []
    for capability_id, handler, is_agent in bindings:
        contract = _contract(
            capability_id,
            f"OIS structural fabric capability: {capability_id}",
            agent=is_agent,
        )
        registry.register(FabricCapability(capability_id, handler, contract))
        registered.append(capability_id)
    return tuple(registered)
