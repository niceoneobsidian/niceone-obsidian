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
    """Provider adapters return ModelOutput and honor request timeout_seconds."""

    provider_id: str

    def invoke(self, model: str, request: dict[str, Any]) -> ModelOutput:
        """Execute one model request through a provider adapter."""


class ModelOutputError(ValueError):
    """Raised when a provider returns data outside the model-output contract."""


class ModelProviderTimeout(TimeoutError):
    """Raised when a bounded provider request exceeds its configured timeout."""


class ModelProvidersExhausted(RuntimeError):
    """Raised when all bounded compatible model-provider attempts fail."""

    def __init__(self, attempts: int, last_error_type: str | None) -> None:
        self.attempts = attempts
        self.last_error_type = last_error_type
        super().__init__(f"model provider attempts exhausted after {attempts} attempt(s)")


@dataclass(frozen=True)
class ModelOutput:
    """Validated inert model text; this object does not represent executable tools."""

    content: str

    def __post_init__(self) -> None:
        if not isinstance(self.content, str) or not self.content.strip():
            raise ModelOutputError("model output content must be a non-empty string")


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
    max_attempts: int = 3

    def __post_init__(self) -> None:
        if (
            isinstance(self.max_attempts, bool)
            or not isinstance(self.max_attempts, int)
            or self.max_attempts < 1
        ):
            raise ValueError("max_attempts must be >= 1")

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
    ) -> ModelOutput:
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
        attempts = 0
        for route in candidates[: self.max_attempts]:
            attempts += 1
            provider = self.providers.get(route.provider)
            if provider is None:
                last_error = LookupError(f"provider not registered: {route.provider}")
                self.records.append(
                    InferenceRecord(
                        request_id=request_id,
                        provider=route.provider,
                        model=route.model,
                        status="failed",
                        started_at=_now(),
                        latency_ms=0.0,
                        error_type=type(last_error).__name__,
                    )
                )
                continue
            started_at = _now()
            started = monotonic()
            try:
                result = provider.invoke(route.model, {"prompt": prompt, **options})
                if not isinstance(result, ModelOutput):
                    raise ModelOutputError("provider returned an invalid model output type")
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
        raise ModelProvidersExhausted(
            attempts=attempts,
            last_error_type=type(last_error).__name__ if last_error is not None else None,
        ) from last_error
