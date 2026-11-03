"""Governed model routing with health, budget, and deterministic fallback."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
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

    def __post_init__(self) -> None:
        if not self.model_id.strip() or not self.version.strip():
            raise ValueError("model_id and version are required")
        if not isfinite(self.cost_per_1k_tokens) or self.cost_per_1k_tokens < 0:
            raise ValueError("cost_per_1k_tokens must be finite and non-negative")
        if self.max_tokens < 1:
            raise ValueError("max_tokens must be positive")


@dataclass(frozen=True)
class ModelRequest:
    capability: str
    prompt: str
    max_tokens: int = 2048
    budget: float | None = None
    preferred_model: str | None = None

    def __post_init__(self) -> None:
        if not self.capability.strip():
            raise ValueError("capability is required")
        if self.max_tokens < 1:
            raise ValueError("max_tokens must be positive")
        if self.budget is not None and (
            not isfinite(self.budget) or self.budget < 0
        ):
            raise ValueError("budget must be finite and non-negative")


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
            metadata={
                "capabilities": sorted(spec.capabilities),
                "priority": spec.priority,
            },
        )
        self._health[(spec.model_id, spec.version)] = spec.healthy

    def set_health(self, model_id: str, version: str, healthy: bool) -> None:
        self.registry.resolve(model_id, version)
        self._health[(model_id, version)] = healthy

    def resolve(self, request: ModelRequest) -> tuple[ModelSpec, bool]:
        registered = list(self.registry.snapshot())
        candidates = [
            entry.value
            for entry in registered
            if request.capability in entry.value.capabilities
            and self._health.get((entry.id, entry.version), False)
            and request.max_tokens <= entry.value.max_tokens
        ]
        candidates.sort(
            key=lambda model: (
                model.model_id != request.preferred_model
                if request.preferred_model is not None
                else False,
                model.priority,
                model.model_id,
                model.version,
            )
        )
        for candidate in candidates:
            cost = request.max_tokens / 1000 * candidate.cost_per_1k_tokens
            if request.budget is None or cost <= request.budget:
                if request.preferred_model is not None:
                    fallback = candidate.model_id != request.preferred_model
                else:
                    fallback = any(
                        entry.value.model_id != candidate.model_id
                        and request.capability in entry.value.capabilities
                        and entry.value.priority < candidate.priority
                        and (
                            not self._health.get((entry.id, entry.version), False)
                            or request.max_tokens > entry.value.max_tokens
                            or (
                                request.budget is not None
                                and request.max_tokens / 1000
                                * entry.value.cost_per_1k_tokens
                                > request.budget
                            )
                        )
                        for entry in registered
                    )
                return candidate, fallback
        raise ModelGatewayError(
            f"No healthy model satisfies capability={request.capability!r} and budget"
        )

    def invoke(self, request: ModelRequest, **kwargs: Any) -> ModelResponse:
        model, fallback = self.resolve(request)
        started = monotonic()
        output = model.provider.generate(
            model=model.model_id,
            prompt=request.prompt,
            max_tokens=request.max_tokens,
            **kwargs,
        )
        latency_ms = (monotonic() - started) * 1000
        cost = request.max_tokens / 1000 * model.cost_per_1k_tokens
        return ModelResponse(model.model_id, model.version, output, latency_ms, cost, fallback)
