"""Governed model routing with health, budget, and deterministic fallback."""
from __future__ import annotations

from dataclasses import dataclass
from time import monotonic
from typing import Any, Protocol

from ois.registries.core import ModelRegistry


class ModelProvider(Protocol):
    def generate(self, *, model: str, prompt: str, **kwargs: Any) -> Any: ...


@dataclass(frozen=True)
class ModelSpec:
    model_id: str
    version: str
    provider: ModelProvider
    capabilities: frozenset[str] = frozenset()
    priority: int = 100
    cost_per_1k_tokens: float = 0.0
    max_tokens: int = 8192
    healthy: bool = True


@dataclass(frozen=True)
class ModelRequest:
    capability: str
    prompt: str
    max_tokens: int = 2048
    budget: float | None = None
    preferred_model: str | None = None


@dataclass(frozen=True)
class ModelResponse:
    model_id: str
    version: str
    output: Any
    latency_ms: float
    estimated_cost: float
    fallback_used: bool


class ModelGatewayError(RuntimeError):
    pass


class ModelGateway:
    """All model calls resolve through the canonical ModelRegistry."""

    def __init__(self, registry: ModelRegistry | None = None) -> None:
        self.registry = registry or ModelRegistry()
        self._health: dict[tuple[str, str], bool] = {}

    def register(self, spec: ModelSpec) -> None:
        self.registry.register(
            spec.model_id,
            spec.version,
            spec,
            metadata={"capabilities": sorted(spec.capabilities), "priority": spec.priority},
        )
        self._health[(spec.model_id, spec.version)] = spec.healthy

    def set_health(self, model_id: str, version: str, healthy: bool) -> None:
        self.registry.resolve(model_id, version)
        self._health[(model_id, version)] = healthy

    def resolve(self, request: ModelRequest) -> tuple[ModelSpec, bool]:
        candidates = [
            entry.value
            for entry in self.registry.snapshot()
            if request.capability in entry.value.capabilities
            and self._health.get((entry.id, entry.version), False)
            and request.max_tokens <= entry.value.max_tokens
        ]
        if request.preferred_model:
            preferred = [m for m in candidates if m.model_id == request.preferred_model]
            candidates = preferred + [m for m in candidates if m.model_id != request.preferred_model]
        candidates.sort(key=lambda m: (m.priority, m.model_id, m.version))
        for index, candidate in enumerate(candidates):
            cost = request.max_tokens / 1000 * candidate.cost_per_1k_tokens
            if request.budget is None or cost <= request.budget:
                return candidate, index > 0
        raise ModelGatewayError(
            f"No healthy model satisfies capability={request.capability!r} and budget"
        )

    def invoke(self, request: ModelRequest, **kwargs: Any) -> ModelResponse:
        model, fallback = self.resolve(request)
        started = monotonic()
        output = model.provider.generate(
            model=model.model_id, prompt=request.prompt, max_tokens=request.max_tokens, **kwargs
        )
        latency_ms = (monotonic() - started) * 1000
        cost = request.max_tokens / 1000 * model.cost_per_1k_tokens
        return ModelResponse(model.model_id, model.version, output, latency_ms, cost, fallback)
