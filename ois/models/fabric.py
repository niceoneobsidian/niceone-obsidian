from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class ModelRoute:
    """Versioned, policy-ready route selected for one model invocation."""

    route_id: str
    provider_id: str
    model_id: str
    version: str
    capabilities: frozenset[str] = frozenset()
    max_input_classification: str = "public"
    risk_levels: frozenset[str] = frozenset({"low"})
    enabled: bool = True
    priority: int = 100


@dataclass(frozen=True)
class ModelRequest:
    capability_id: str
    input: dict[str, Any]
    risk_level: str = "low"
    data_classification: str = "public"
    required_capabilities: frozenset[str] = frozenset()


@dataclass(frozen=True)
class ModelResponse:
    output: dict[str, Any]
    route: ModelRoute
    usage: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)


class ModelProvider(Protocol):
    provider_id: str

    def invoke(self, route: ModelRoute, request: ModelRequest) -> ModelResponse:
        ...


class ModelRegistry:
    """Canonical registry for model routes and their providers."""

    def __init__(self) -> None:
        self._routes: dict[str, ModelRoute] = {}
        self._providers: dict[str, ModelProvider] = {}

    def register(self, route: ModelRoute, provider: ModelProvider) -> None:
        if route.provider_id != provider.provider_id:
            raise ValueError("route provider_id must match provider.provider_id")
        if route.route_id in self._routes:
            raise ValueError(f"model route already registered: {route.route_id}")
        self._routes[route.route_id] = route
        self._providers[route.provider_id] = provider

    def routes(self) -> tuple[ModelRoute, ...]:
        return tuple(self._routes.values())

    def provider(self, provider_id: str) -> ModelProvider:
        try:
            return self._providers[provider_id]
        except KeyError as exc:
            raise KeyError(f"model provider not registered: {provider_id}") from exc


class ModelRouter:
    """Deterministic eligibility-first model routing."""

    _classification_rank = {
        "public": 0,
        "internal": 1,
        "confidential": 2,
        "restricted": 3,
    }

    def __init__(self, registry: ModelRegistry) -> None:
        self.registry = registry

    def select(self, request: ModelRequest) -> ModelRoute:
        candidates = [route for route in self.registry.routes() if route.enabled]
        eligible = [route for route in candidates if self._eligible(route, request)]
        if not eligible:
            raise LookupError("no eligible model route for request")
        return sorted(eligible, key=lambda route: (route.priority, route.route_id))[0]

    def _eligible(self, route: ModelRoute, request: ModelRequest) -> bool:
        if request.risk_level not in route.risk_levels:
            return False
        if self._classification_rank[request.data_classification] > self._classification_rank[
            route.max_input_classification
        ]:
            return False
        return request.required_capabilities.issubset(route.capabilities)


class LLMGateway:
    """Single model execution boundary used by OIS agents."""

    def __init__(self, registry: ModelRegistry) -> None:
        self.router = ModelRouter(registry)
        self.registry = registry

    def invoke(self, request: ModelRequest) -> ModelResponse:
        route = self.router.select(request)
        provider = self.registry.provider(route.provider_id)
        return provider.invoke(route, request)


class DeterministicTestProvider:
    """Offline provider used to prove the model fabric without credentials."""

    provider_id = "deterministic.test"

    def invoke(self, route: ModelRoute, request: ModelRequest) -> ModelResponse:
        topic = str(request.input.get("topic", "")).strip()
        if not topic:
            raise ValueError("topic is required")
        objective = str(request.input.get("objective", "education"))
        tone = str(request.input.get("tone", "clear"))
        hook = f"Start with this practical point about {topic}."
        return ModelResponse(
            output={
                "topic": topic,
                "objective": objective,
                "tone": tone,
                "hook": hook,
                "provider_generated": True,
            },
            route=route,
            usage={"input_units": len(topic.split()), "output_units": len(hook.split())},
            metadata={"provider_mode": "deterministic_test"},
        )
