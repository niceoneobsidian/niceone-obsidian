"""Provider adapter interfaces for design capabilities.

Concrete integrations implement these protocols. The kernel depends only on
these interfaces and never on a specific vendor.
"""

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class AdapterRequest:
    capability_id: str
    workflow_id: str
    inputs: dict[str, Any]
    constraints: dict[str, Any] = field(default_factory=dict)
    references: tuple[str, ...] = ()


@dataclass(frozen=True)
class AdapterResponse:
    status: str
    outputs: dict[str, Any]
    provider: str
    model: str | None = None
    trace_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


class TextModelProvider(Protocol):
    def generate(self, request: AdapterRequest) -> AdapterResponse: ...


class ImageGenerationProvider(Protocol):
    def generate(self, request: AdapterRequest) -> AdapterResponse: ...


class ImageEditingProvider(Protocol):
    def edit(self, request: AdapterRequest) -> AdapterResponse: ...


class VideoProvider(Protocol):
    def generate(self, request: AdapterRequest) -> AdapterResponse: ...
    def edit(self, request: AdapterRequest) -> AdapterResponse: ...


class MotionProvider(Protocol):
    def render(self, request: AdapterRequest) -> AdapterResponse: ...


class DesignRendererProvider(Protocol):
    def render(self, request: AdapterRequest) -> AdapterResponse: ...


class DocumentRendererProvider(Protocol):
    def render(self, request: AdapterRequest) -> AdapterResponse: ...


class ProductionProvider(Protocol):
    def preflight(self, request: AdapterRequest) -> AdapterResponse: ...


class VisionQAProvider(Protocol):
    def inspect(self, request: AdapterRequest) -> AdapterResponse: ...


class AdapterRegistry:
    """Runtime registry for provider adapters."""

    def __init__(self) -> None:
        self._adapters: dict[str, Any] = {}

    def register(self, adapter_id: str, adapter: Any) -> None:
        if adapter_id in self._adapters:
            raise ValueError(f"Adapter already registered: {adapter_id}")
        self._adapters[adapter_id] = adapter

    def resolve(self, adapter_id: str) -> Any:
        try:
            return self._adapters[adapter_id]
        except KeyError as exc:
            raise KeyError(f"No adapter registered: {adapter_id}") from exc

    def registered(self) -> tuple[str, ...]:
        return tuple(sorted(self._adapters))
