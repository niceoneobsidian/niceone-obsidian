"""Design capability execution adapters."""

from dataclasses import dataclass
from typing import Any, Protocol

from ois.kernel.state import ExecutionContext
from ois.design_intelligence.catalog import DesignCapability, get_capability


class DesignProvider(Protocol):
    def execute(self, capability: DesignCapability, context: ExecutionContext) -> Any: ...


@dataclass
class DesignExecutionResult:
    capability_id: str
    status: str
    output: Any = None
    evidence: list[str] | None = None
    validation: list[str] | None = None


class DesignCapabilityFabric:
    """Routes design capability requests to registered providers."""

    def __init__(self) -> None:
        self._providers: dict[str, DesignProvider] = {}

    def register_provider(self, capability_id: str, provider: DesignProvider) -> None:
        get_capability(capability_id)
        if capability_id in self._providers:
            raise ValueError(f"Provider already registered: {capability_id}")
        self._providers[capability_id] = provider

    def execute(self, capability_id: str, context: ExecutionContext) -> DesignExecutionResult:
        capability = get_capability(capability_id)
        provider = self._providers.get(capability_id)
        if provider is None:
            return DesignExecutionResult(
                capability_id=capability_id,
                status="unbound",
                evidence=list(capability.evidence),
                validation=list(capability.validation),
            )
        output = provider.execute(capability, context)
        return DesignExecutionResult(
            capability_id=capability_id,
            status="executed",
            output=output,
            evidence=list(capability.evidence),
            validation=list(capability.validation),
        )
