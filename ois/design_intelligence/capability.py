from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class DesignCapability:
    id: str
    domain: str
    name: str
    description: str
    modalities: tuple[str, ...] = ()
    requirements: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


class DesignProvider(Protocol):
    def execute(self, capability: DesignCapability, inputs: dict[str, Any]) -> Any: ...


class DesignCapabilityFabric:
    """Domain-facing capability catalog; providers remain pluggable."""

    def __init__(self) -> None:
        self._capabilities: dict[str, DesignCapability] = {}

    def register(self, capability: DesignCapability) -> None:
        if capability.id in self._capabilities:
            raise ValueError(f"Design capability already registered: {capability.id}")
        self._capabilities[capability.id] = capability

    def get(self, capability_id: str) -> DesignCapability:
        return self._capabilities[capability_id]

    def by_domain(self, domain: str) -> tuple[DesignCapability, ...]:
        return tuple(c for c in self._capabilities.values() if c.domain == domain)
