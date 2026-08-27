"""Provider-neutral LLM gateway runtime for OIS.

The gateway performs deterministic route selection and records inference
telemetry. Provider adapters remain outside the Kernel; authorization,
validation, evidence and recovery stay owned by OIS runtime boundaries.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from time import monotonic
from typing import Any, Protocol

from ois.architecture.fabrics import LLMGatewaySpec, ModelRoute


def _now() -> str:
    return datetime.now(UTC).isoformat()


class LLMProvider(Protocol):
    provider_id: str

    def invoke(self, model: str, request: dict[str, Any]) -> Any:
        """Execute one model request through a provider adapter."""


@dataclass(frozen=True)
class InferenceRecord:
    request_id: str
    provider: str
    model: str
    status: str
    started_at: str
    latency_ms: float
    input_tokens: int | None = None
    output_tokens: int | None = None
    cost: float | None = None
    error_type: str | None = None


@dataclass
class LLMGateway:
    """Deterministic provider gateway with bounded fallback."""

    spec: LLMGatewaySpec
    routes: list[ModelRoute] = field(default_factory=list)
    providers: dict[str, LLMProvider] = field(default_factory=dict)
    records: list[InferenceRecord] = field(default_factory=list)

    def register_route(self, route: ModelRoute) -> None:
        self.routes.append(route)
        self.routes.sort(key=lambda item: (item.provider, item.model, item.version))

    def register_provider(self, provider: LLMProvider) -> None:
        self.providers[provider.provider_id] = provider

    def route(
        self,
        capabilities: set[str],
        constraints: dict[str, Any] | None = None,
    ) -> ModelRoute:
        constraints = constraints or {}
        candidates = [
            route
            for route in self.routes
            if capabilities.issubset(route.capabilities)
            and all(route.constraints.get(key) == value for key, value in constraints.items())
        ]
        if not candidates:
            raise LookupError(f"no model route satisfies capabilities={sorted(capabilities)}")
        return min(
            candidates,
            key=lambda item: (sum(item.cost_profile.values()), item.provider, item.model),
        )

    def invoke(
        self,
        request_id: str,
        prompt: str,
        *,
        capabilities: set[str] | None = None,
        options: dict[str, Any] | None = None,
    ) -> Any:
        options = dict(options or {})
        capabilities = set(capabilities or ())
        selected = self.route(capabilities, options.get("constraints"))
        candidates = [selected]
        if self.spec.fallback_policy == "next_compatible":
            candidates.extend(
                route
                for route in self.routes
                if route != selected
                and capabilities.issubset(route.capabilities)
                and all(
                    route.constraints.get(key) == value
                    for key, value in options.get("constraints", {}).items()
                )
            )

        last_error: Exception | None = None
        for route in candidates:
            provider = self.providers.get(route.provider)
            if provider is None:
                last_error = LookupError(f"provider not registered: {route.provider}")
                continue
            started_at = _now()
            started = monotonic()
            try:
                result = provider.invoke(route.model, {"prompt": prompt, **options})
            except Exception as exc:
                last_error = exc
                self.records.append(
                    InferenceRecord(
                        request_id=request_id,
                        provider=route.provider,
                        model=route.model,
                        status="failed",
                        started_at=started_at,
                        latency_ms=(monotonic() - started) * 1000,
                        error_type=type(exc).__name__,
                    )
                )
                continue
            self.records.append(
                InferenceRecord(
                    request_id=request_id,
                    provider=route.provider,
                    model=route.model,
                    status="succeeded",
                    started_at=started_at,
                    latency_ms=(monotonic() - started) * 1000,
                )
            )
            return result
        if last_error is not None:
            raise last_error
        raise LookupError("no usable model provider")
