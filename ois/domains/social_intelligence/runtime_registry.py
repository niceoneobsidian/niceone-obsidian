"""Authoritative registration of Social Intelligence in the OIS Kernel."""
from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ois.kernel.contracts import AgentContract, InvocationRequest, InvocationResult, ToolContract
from ois.kernel.registry import AgentRegistry, CapabilityRegistry, ToolRegistry
from ois.kernel.types import RiskLevel, SideEffectLevel

from .kernel_integration import register_social_kernel_capabilities
from .platform_adapters import SocialConnector
from .runtime_capabilities import SOCIAL_RUNTIME_CAPABILITIES


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


def register_social_runtime(
    capabilities: CapabilityRegistry,
    agents: AgentRegistry,
    tools: ToolRegistry,
    *,
    connectors: Any,
    tokenized_tools: bool = True,
) -> dict[str, int]:
    """Register executable M13-M20 capabilities and social agent/tool providers.

    The function is intentionally explicit and idempotency-safe: duplicate
    registrations are surfaced by the canonical Kernel registries instead of
    being silently overwritten.
    """
    register_social_kernel_capabilities(capabilities, connectors=connectors)
    registered_capabilities = 2

    providers = [capability() for capability in SOCIAL_RUNTIME_CAPABILITIES]
    for provider in providers:
        capabilities.register(provider)
        registered_capabilities += 1
        agents.register(_agent_for(provider))

    if tokenized_tools:
        for platform in connectors.platforms():
            connector = connectors.get(platform)
            tool = ConnectorTool(connector)
            tools.register(tool)

    return {
        "capabilities": registered_capabilities,
        "agents": len(providers),
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
            status=__import__("ois.kernel.types", fromlist=["InvocationStatus"]).InvocationStatus.SUCCEEDED,
            output={"platform_result": result},
        )
