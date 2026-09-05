"""Authoritative registration of Social Intelligence in the OIS Kernel."""

from __future__ import annotations

from typing import Any

from ois.kernel.contracts import AgentContract, InvocationRequest, InvocationResult, ToolContract
from ois.kernel.registry import AgentRegistry, CapabilityRegistry, ToolRegistry
from ois.kernel.types import InvocationStatus, RiskLevel, SideEffectLevel
from ois.runtime.llm_gateway import LLMGateway

from .kernel_integration import SocialIngestCapability, SocialResearchCapability
from .model_gateway import GatewayBackedM15Prediction
from .platform_adapters import SocialConnector
from .runtime_capabilities import M15Prediction, SOCIAL_RUNTIME_CAPABILITIES


class DelegatingSocialAgent:
    """Agent provider that delegates execution to a registered capability provider."""

    def __init__(self, capability: Any, contract: AgentContract) -> None:
        self._capability = capability
        self._contract = contract

    @property
    def contract(self) -> AgentContract:
        return self._contract

    def invoke(self, request: InvocationRequest) -> InvocationResult:
        return self._capability.invoke(request)


def _agent_for(capability: Any) -> DelegatingSocialAgent:
    base = capability.contract
    contract = AgentContract(
        capability_id=f"social.agent.{base.capability_id.removeprefix('social.')}",
        version="1.0.0",
        description=f"Agent provider for {base.capability_id}@{base.version}",
        input_schema=base.input_schema,
        output_schema=base.output_schema,
        risk_level=base.risk_level,
        permissions=base.permissions,
        allowed_domains=base.allowed_domains,
        timeout_seconds=base.timeout_seconds,
        max_retries=base.max_retries,
        side_effects=base.side_effects,
        idempotent=base.idempotent,
        model_requirements={"gateway": "ois.model_gateway", "mode": "deterministic-or-provider"},
        max_iterations=1,
    )
    return DelegatingSocialAgent(capability, contract)


class SocialCapabilityRegistry:
    """Domain facade over the canonical OIS Kernel CapabilityRegistry."""

    capability_ids = (
        "social.ingest", "social.research.execute", "social.content.intelligence",
        "social.content.predict", "social.experiment.simulate", "social.learning.compare_outcome",
        "social.learning.pattern_extract", "social.campaign.optimize", "social.evolution.propose",
    )

    def __init__(self, kernel_registry: CapabilityRegistry) -> None:
        self.kernel_registry = kernel_registry

    def activate(
        self,
        agents: AgentRegistry,
        tools: ToolRegistry,
        *,
        connectors: Any,
        model_gateway: LLMGateway | None = None,
    ) -> dict[str, int]:
        return register_social_runtime(
            self.kernel_registry,
            agents,
            tools,
            connectors=connectors,
            model_gateway=model_gateway,
        )

    def entries(self):
        return tuple(
            entry
            for entry in self.kernel_registry.list()
            if entry.contract.capability_id in self.capability_ids
        )


def register_social_runtime(
    capabilities: CapabilityRegistry,
    agents: AgentRegistry,
    tools: ToolRegistry,
    *,
    connectors: Any,
    tokenized_tools: bool = True,
    model_gateway: LLMGateway | None = None,
) -> dict[str, int]:
    """Register executable M13-M20 capabilities and social agent/tool providers."""
    m13_providers = [SocialIngestCapability(connectors), SocialResearchCapability()]
    for provider in m13_providers:
        capabilities.register(provider)
        agents.register(_agent_for(provider))

    providers: list[Any] = []
    for capability in SOCIAL_RUNTIME_CAPABILITIES:
        provider = (
            GatewayBackedM15Prediction(model_gateway)
            if capability is M15Prediction and model_gateway is not None
            else capability()
        )
        providers.append(provider)
        capabilities.register(provider)
        agents.register(_agent_for(provider))

    if tokenized_tools:
        for platform in connectors.platforms():
            tools.register(ConnectorTool(connectors.get(platform)))

    return {
        "capabilities": len(m13_providers) + len(providers),
        "agents": len(m13_providers) + len(providers),
        "tools": len(connectors.platforms()) if tokenized_tools else 0,
    }


class ConnectorTool:
    """Kernel ToolContract wrapper around an authorized SocialConnector."""

    def __init__(self, connector: SocialConnector) -> None:
        self._connector = connector
        self._contract = ToolContract(
            capability_id=f"social.tool.{connector.platform}.publish",
            version="1.0.0",
            description=f"Invoke the {connector.platform} publishing adapter through the Kernel tool boundary.",
            input_schema={"publish_intent": "object"},
            output_schema={"platform_result": "object"},
            risk_level=RiskLevel.HIGH,
            permissions=("social.publish",),
            allowed_domains=("social_intelligence", "social_growth"),
            timeout_seconds=60.0,
            max_retries=0,
            side_effects=SideEffectLevel.IRREVERSIBLE,
            idempotent=False,
            requires_approval=True,
        )

    @property
    def contract(self) -> ToolContract:
        return self._contract

    def invoke(self, request: InvocationRequest) -> InvocationResult:
        from .schemas import PublishIntent

        intent = PublishIntent.model_validate(request.input.get("publish_intent"))
        result = self._connector.publish(intent)
        return InvocationResult(
            invocation_id=request.invocation_id,
            capability_id=self.contract.capability_id,
            status=InvocationStatus.SUCCEEDED,
            output={"platform_result": result},
        )
