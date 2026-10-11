"""Governed provider execution path: Tool -> Capability -> Policy -> Provider.

Every step fails closed. Nothing reaches a provider adapter unless the tool is
registered, its capability contract is registered and identical in the
governance-relevant fields, the provider is registered and enabled in the
canonical ``SourceAdapterRegistry``, the operation is read-only, the policy
engine allows it (checked again immediately before the call), and required
credential references are present. Registry presence alone grants nothing.

This module only orders and enforces checks over the existing registries. It does
not resolve credentials (Stage 4), perform network I/O itself, or add providers.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from ois.infrastructure.source_adapters.base import AdapterResult, SourceAdapterRegistry
from ois.infrastructure.source_gateway.gateway import SourceGateway
from ois.kernel.contracts import CapabilityContract, InvocationRequest, PolicyEngine, ToolContract
from ois.kernel.policy import PolicyDecision
from ois.kernel.types import SideEffectLevel
from ois.registries.core import CapabilityRegistry, ToolRegistry

_CONTRACT_FIELDS = ("permissions", "risk_level", "side_effects", "idempotent", "allowed_domains")


class PathOutcome(StrEnum):
    EXECUTED = "EXECUTED"
    DENIED = "DENIED"
    FAILED = "FAILED"


@dataclass(frozen=True)
class PathStep:
    name: str
    passed: bool
    detail: str = ""


@dataclass(frozen=True)
class ProviderPathResult:
    outcome: PathOutcome
    capability_id: str
    source_id: str | None
    steps: tuple[PathStep, ...]
    reason: str | None = None
    adapter_result: AdapterResult | None = None

    @property
    def executed(self) -> bool:
        return self.outcome is PathOutcome.EXECUTED


class ProviderExecutionPath:
    def __init__(
        self,
        *,
        tools: ToolRegistry,
        capabilities: CapabilityRegistry,
        sources: SourceAdapterRegistry,
        policy: PolicyEngine,
        gateway: SourceGateway,
    ) -> None:
        self._tools = tools
        self._capabilities = capabilities
        self._sources = sources
        self._policy = policy
        self._gateway = gateway

    def execute(
        self,
        request: InvocationRequest,
        *,
        version: str,
        workspace_id: str,
        credential_id: str | None = None,
    ) -> ProviderPathResult:
        steps: list[PathStep] = []
        capability_id = request.capability_id

        def deny(reason: str, source_id: str | None = None) -> ProviderPathResult:
            steps.append(PathStep(reason.split(":", 1)[0], False, reason))
            return ProviderPathResult(
                PathOutcome.DENIED, capability_id, source_id, tuple(steps), reason
            )

        if not workspace_id:
            return deny("workspace-missing")
        if not request.execution.identity.tenant_id:
            return deny("tenant-missing")

        # 1. Tool
        if not self._tools.has(capability_id, version):
            return deny("tool-not-registered")
        entry = self._tools.get(capability_id, version)
        tool_contract = entry.contract
        source_id = getattr(entry.capability, "source_id", None)
        if not isinstance(tool_contract, ToolContract) or not source_id:
            return deny("tool-descriptor-invalid")
        steps.append(PathStep("tool", True, f"{capability_id}@{version}"))

        # 2. Capability (must exist and agree with the tool contract)
        if not self._capabilities.has(capability_id, version):
            return deny("capability-not-registered", source_id)
        capability = self._capabilities.get(capability_id, version).capability
        if not isinstance(capability, CapabilityContract):
            return deny("capability-contract-invalid", source_id)
        differing = [
            f for f in _CONTRACT_FIELDS if getattr(capability, f) != getattr(tool_contract, f)
        ]
        if differing:
            return deny("contract-mismatch:" + ",".join(differing), source_id)
        steps.append(PathStep("capability", True, capability_id))

        # 3. Read-only only: no side-effecting tool is executable in this path.
        if tool_contract.side_effects is not SideEffectLevel.NONE:
            return deny("side-effects-not-permitted", source_id)
        steps.append(PathStep("read-only", True))

        # 4. Provider must be registered and enabled in the canonical registry.
        if source_id not in self._sources.list():
            return deny("provider-not-registered", source_id)
        if not self._sources.spec(source_id).enabled:
            return deny("provider-disabled", source_id)
        steps.append(PathStep("provider-registered", True, source_id))

        # 5. Policy (planning-time check).
        refusal = self._policy_refusal(request, tool_contract)
        if refusal:
            return deny(refusal, source_id)
        steps.append(PathStep("policy", True))

        # 6. Credential reference presence (resolution itself is Stage 4).
        if tool_contract.secrets_required and not credential_id:
            return deny("credential-reference-missing", source_id)
        steps.append(PathStep("credential-reference", True))

        # 7. Cancellation, then policy re-check immediately before the provider call.
        cancellation = request.cancellation
        if cancellation is not None:
            try:
                cancellation.raise_if_cancelled()
            except Exception as exc:
                steps.append(PathStep("cancellation", False, type(exc).__name__))
                return ProviderPathResult(
                    PathOutcome.FAILED, capability_id, source_id, tuple(steps), "cancelled"
                )
        refusal = self._policy_refusal(request, tool_contract)
        if refusal:
            return deny("recheck-" + refusal, source_id)
        steps.append(PathStep("policy-recheck", True))

        # 8. Provider boundary.
        try:
            result: Any = self._sources.get(source_id).ingest(
                tenant_id=request.execution.identity.tenant_id,
                workspace_id=workspace_id,
                gateway=self._gateway,
                credential_id=credential_id,
            )
        except Exception as exc:
            steps.append(PathStep("provider-call", False, type(exc).__name__))
            return ProviderPathResult(
                PathOutcome.FAILED,
                capability_id,
                source_id,
                tuple(steps),
                f"provider-error:{type(exc).__name__}",
            )
        if not isinstance(result, AdapterResult):
            steps.append(PathStep("provider-call", False, "invalid-result"))
            return ProviderPathResult(
                PathOutcome.FAILED,
                capability_id,
                source_id,
                tuple(steps),
                "provider-invalid-result",
            )
        steps.append(PathStep("provider-call", True, f"records={result.records}"))
        return ProviderPathResult(
            PathOutcome.EXECUTED, capability_id, source_id, tuple(steps), None, result
        )

    def _policy_refusal(self, request: InvocationRequest, contract: ToolContract) -> str | None:
        evaluate = getattr(self._policy, "evaluate", None)
        if not callable(evaluate):
            return "policy-engine-unavailable"
        try:
            decision = evaluate(request, contract)
        except Exception as exc:
            return f"policy-error:{type(exc).__name__}"
        if not isinstance(decision, PolicyDecision):
            return "policy-invalid-decision"
        if not decision.allowed:
            return "policy-denied:" + "; ".join(decision.reasons)
        if decision.requires_approval or contract.requires_approval:
            return "approval-required"
        return None
