"""Stage 3: Tool -> Capability -> Policy -> Provider, authorized and denied paths.

Fake adapters only: these tests prove the governance ordering, not live provider
behaviour. Nothing here is live, E2E or production evidence.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from ois.infrastructure.source_adapters.base import AdapterResult, SourceAdapterRegistry
from ois.infrastructure.source_adapters.bootstrap import (
    build_application_source_adapter_registry,
)
from ois.infrastructure.source_gateway.gateway import SourceGateway
from ois.integration.inventory_drift import compare_inventory_to_registry
from ois.integration.provider_execution_path import (
    PathOutcome,
    ProviderExecutionPath,
)
from ois.integrations.provider_contracts import (
    PROVIDER_CAPABILITIES,
    build_provider_capability_registry,
)
from ois.integrations.provider_tools import (
    PROVIDER_TOOLS,
    ProviderToolDescriptor,
    build_provider_tool_registry,
)
from ois.kernel.contracts import InvocationRequest, ToolContract
from ois.kernel.policy import DefaultPolicyEngine, PolicyDecision
from ois.kernel.state import ExecutionContext, ExecutionIdentity
from ois.kernel.types import RiskLevel, SideEffectLevel
from ois.registries.core import CapabilityRegistry, ToolRegistry

ROOT = Path(__file__).resolve().parents[2]
REAL = build_application_source_adapter_registry()
REGISTERED = list(REAL.list())
TOOL_FOR = {d.source_id: d for d in PROVIDER_TOOLS}
PERMS = {sid: TOOL_FOR[sid].contract.permissions for sid in REGISTERED}
ALL_PERMS = {p for perms in PERMS.values() for p in perms}


class FakeAdapter:
    def __init__(self, source_id: str, error: Exception | None = None, result: Any = "ok") -> None:
        self.source_id = source_id
        self.calls: list[dict[str, Any]] = []
        self._error = error
        self._result = result

    def ingest(self, **kwargs: Any) -> AdapterResult:
        self.calls.append(kwargs)
        if self._error:
            raise self._error
        if self._result != "ok":
            return self._result
        return AdapterResult(self.source_id, 1, ("e1",), ("v1",), ("h1",))


def _sources(
    *, adapters: dict[str, FakeAdapter] | None = None, disabled: str | None = None
) -> tuple[SourceAdapterRegistry, dict[str, FakeAdapter]]:
    registry = SourceAdapterRegistry()
    fakes = adapters or {sid: FakeAdapter(sid) for sid in REGISTERED}
    for sid, fake in fakes.items():
        spec = REAL.spec(sid)
        if sid == disabled:
            spec = replace(spec, enabled=False)
        registry.register(fake, spec)
    return registry, fakes


def _path(
    *,
    policy: Any = None,
    tools: ToolRegistry | None = None,
    capabilities: CapabilityRegistry | None = None,
    sources: SourceAdapterRegistry | None = None,
) -> tuple[ProviderExecutionPath, dict[str, FakeAdapter]]:
    reg, fakes = (sources, {}) if sources else _sources()
    path = ProviderExecutionPath(
        tools=tools or build_provider_tool_registry(),
        capabilities=capabilities or build_provider_capability_registry(),
        sources=reg,
        policy=policy or DefaultPolicyEngine(allowed_permissions=ALL_PERMS),
        gateway=SourceGateway(),
    )
    return path, fakes


def _request(sid: str, tenant: str = "tenant-a", cancellation: Any = None) -> InvocationRequest:
    return InvocationRequest(
        invocation_id="inv-1",
        capability_id=TOOL_FOR[sid].contract.capability_id,
        input={},
        execution=ExecutionContext(ExecutionIdentity(tenant_id=tenant), objective="read"),
        cancellation=cancellation,
    )


def _run(path: ProviderExecutionPath, sid: str, **kw: Any):
    args = {"version": "1.0.0", "workspace_id": "ws-1", "credential_id": "cred-1"}
    request = kw.pop("request", None) or _request(sid)
    args.update(kw)
    return path.execute(request, **args)


# ---- authorized path -------------------------------------------------------


@pytest.mark.parametrize("sid", REGISTERED)
def test_authorized_read_traverses_every_gate_in_order(sid: str) -> None:
    path, fakes = _path()
    result = _run(path, sid)
    assert result.outcome is PathOutcome.EXECUTED and result.executed
    assert [s.name for s in result.steps] == [
        "tool",
        "capability",
        "read-only",
        "provider-registered",
        "policy",
        "credential-reference",
        "policy-recheck",
        "provider-call",
    ]
    assert all(s.passed for s in result.steps)
    assert len(fakes[sid].calls) == 1
    call = fakes[sid].calls[0]
    assert (call["tenant_id"], call["workspace_id"], call["credential_id"]) == (
        "tenant-a",
        "ws-1",
        "cred-1",
    )
    assert all(len(f.calls) == 0 for s, f in fakes.items() if s != sid)


# ---- denials: provider never called ---------------------------------------


def _assert_denied(result: Any, fakes: dict[str, FakeAdapter], reason: str) -> None:
    assert result.outcome is PathOutcome.DENIED and not result.executed
    assert result.reason is not None and reason in result.reason
    assert result.adapter_result is None
    assert all(len(f.calls) == 0 for f in fakes.values())
    assert result.steps[-1].passed is False


@pytest.mark.parametrize("sid", REGISTERED)
def test_missing_permission_is_denied(sid: str) -> None:
    path, fakes = _path(policy=DefaultPolicyEngine(allowed_permissions=ALL_PERMS - set(PERMS[sid])))
    _assert_denied(_run(path, sid), fakes, "policy-denied:Missing permissions")


@pytest.mark.parametrize("sid", REGISTERED)
def test_empty_policy_allowlist_denies_everything(sid: str) -> None:
    path, fakes = _path(policy=DefaultPolicyEngine())
    _assert_denied(_run(path, sid), fakes, "policy-denied")


@pytest.mark.parametrize("sid", REGISTERED)
def test_missing_tenant_is_denied(sid: str) -> None:
    path, fakes = _path()
    _assert_denied(_run(path, sid, request=_request(sid, tenant="")), fakes, "tenant-missing")


def test_missing_workspace_is_denied() -> None:
    path, fakes = _path()
    _assert_denied(_run(path, REGISTERED[0], workspace_id=""), fakes, "workspace-missing")


@pytest.mark.parametrize("sid", [s for s in REGISTERED if TOOL_FOR[s].contract.secrets_required])
def test_missing_credential_reference_is_denied(sid: str) -> None:
    path, fakes = _path()
    _assert_denied(_run(path, sid, credential_id=None), fakes, "credential-reference-missing")


def test_unknown_tool_and_wrong_version_are_denied() -> None:
    path, fakes = _path()
    request = InvocationRequest(
        "i", "provider.unknown.tool", {}, ExecutionContext(ExecutionIdentity(tenant_id="t"), "x")
    )
    _assert_denied(
        path.execute(request, version="1.0.0", workspace_id="w"), fakes, "tool-not-registered"
    )
    _assert_denied(_run(path, REGISTERED[0], version="9.9.9"), fakes, "tool-not-registered")


def test_tool_without_capability_is_denied() -> None:
    sid = REGISTERED[0]
    caps = CapabilityRegistry()
    for contract in PROVIDER_CAPABILITIES:
        if contract.capability_id != TOOL_FOR[sid].contract.capability_id:
            caps.register(contract.capability_id, contract.version, contract)
    path, fakes = _path(capabilities=caps)
    _assert_denied(_run(path, sid), fakes, "capability-not-registered")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("permissions", ("something.else",)),
        ("risk_level", RiskLevel.HIGH),
        ("side_effects", SideEffectLevel.REVERSIBLE),
        ("allowed_domains", ("other",)),
    ],
)
def test_capability_contract_drift_from_tool_is_denied(field: str, value: Any) -> None:
    sid = REGISTERED[0]
    caps = CapabilityRegistry()
    for contract in PROVIDER_CAPABILITIES:
        if contract.capability_id == TOOL_FOR[sid].contract.capability_id:
            contract = replace(contract, **{field: value})
        caps.register(contract.capability_id, contract.version, contract)
    path, fakes = _path(capabilities=caps)
    _assert_denied(_run(path, sid), fakes, f"contract-mismatch:{field}")


def _tools_with(sid: str, **changes: Any) -> ToolRegistry:
    tools = ToolRegistry()
    for descriptor in PROVIDER_TOOLS:
        if descriptor.source_id == sid:
            descriptor = ProviderToolDescriptor(replace(descriptor.contract, **changes), sid)
        tools.register(descriptor.contract.capability_id, "1.0.0", descriptor)
    return tools


def _caps_matching(sid: str, **changes: Any) -> CapabilityRegistry:
    caps = CapabilityRegistry()
    for contract in PROVIDER_CAPABILITIES:
        if contract.capability_id == TOOL_FOR[sid].contract.capability_id:
            contract = replace(contract, **changes)
        caps.register(contract.capability_id, contract.version, contract)
    return caps


def test_side_effecting_tool_is_denied_even_if_capability_agrees() -> None:
    sid = REGISTERED[0]
    change = {"side_effects": SideEffectLevel.REVERSIBLE}
    path, fakes = _path(
        tools=_tools_with(sid, **change), capabilities=_caps_matching(sid, **change)
    )
    _assert_denied(_run(path, sid), fakes, "side-effects-not-permitted")


def test_high_risk_tool_beyond_policy_limit_is_denied() -> None:
    sid = REGISTERED[0]
    change = {"risk_level": RiskLevel.CRITICAL}
    path, fakes = _path(
        tools=_tools_with(sid, **change), capabilities=_caps_matching(sid, **change)
    )
    _assert_denied(_run(path, sid), fakes, "policy-denied:Capability risk exceeds")


def test_approval_required_tool_is_denied_without_an_approval_mechanism() -> None:
    sid = REGISTERED[0]
    path, fakes = _path(tools=_tools_with(sid, requires_approval=True))
    _assert_denied(_run(path, sid), fakes, "approval-required")


def test_provider_disabled_is_denied() -> None:
    sources, fakes = _sources(disabled=REGISTERED[1])
    path, _ = _path(sources=sources)
    _assert_denied(_run(path, REGISTERED[1]), fakes, "provider-disabled")


def test_tool_whose_provider_is_not_registered_is_denied() -> None:
    """tiktok/rss tools exist in the ToolRegistry but have no registered provider."""
    unregistered = [d for d in PROVIDER_TOOLS if d.source_id not in REGISTERED]
    assert unregistered, "expected tools whose provider is not registered"
    path, fakes = _path()
    for descriptor in unregistered:
        request = InvocationRequest(
            "i",
            descriptor.contract.capability_id,
            {},
            ExecutionContext(ExecutionIdentity(tenant_id="t"), "x"),
        )
        result = path.execute(request, version="1.0.0", workspace_id="w", credential_id="c")
        _assert_denied(result, fakes, "provider-not-registered")


def test_tools_without_registered_provider_are_all_explained_by_the_backlog() -> None:
    orphans = {d.source_id for d in PROVIDER_TOOLS} - set(REGISTERED)
    drift = compare_inventory_to_registry(ROOT, REAL)
    assert orphans <= set(drift.explained)


def test_every_registered_provider_has_exactly_one_tool_and_capability() -> None:
    tools = build_provider_tool_registry()
    caps = build_provider_capability_registry()
    for sid in REGISTERED:
        matching = [d for d in PROVIDER_TOOLS if d.source_id == sid]
        assert len(matching) == 1
        cid = matching[0].contract.capability_id
        assert tools.has(cid, "1.0.0") and caps.has(cid, "1.0.0")


# ---- policy behaviour ------------------------------------------------------


class _FlipPolicy:
    """Allows the planning-time check, then denies the pre-effect re-check."""

    def __init__(self) -> None:
        self.calls = 0

    def evaluate(self, request: Any, contract: Any) -> PolicyDecision:
        self.calls += 1
        if self.calls == 1:
            return PolicyDecision(True)
        return PolicyDecision(False, ("revoked after planning",))

    def authorize(self, request: Any, contract: Any) -> bool:  # pragma: no cover
        return True


def test_policy_is_rechecked_immediately_before_the_provider_call() -> None:
    policy = _FlipPolicy()
    path, fakes = _path(policy=policy)
    result = _run(path, REGISTERED[0])
    _assert_denied(result, fakes, "recheck-policy-denied")
    assert policy.calls == 2


@pytest.mark.parametrize(
    "policy",
    [object(), type("Boom", (), {"evaluate": lambda s, r, c: 1 / 0})()],
)
def test_broken_or_missing_policy_engine_fails_closed(policy: Any) -> None:
    path, fakes = _path(policy=policy)
    result = _run(path, REGISTERED[0])
    assert result.outcome is PathOutcome.DENIED
    assert all(len(f.calls) == 0 for f in fakes.values())


def test_policy_returning_non_decision_fails_closed() -> None:
    policy = type("Weird", (), {"evaluate": lambda s, r, c: True})()
    path, fakes = _path(policy=policy)
    _assert_denied(_run(path, REGISTERED[0]), fakes, "policy-invalid-decision")


# ---- failures at the provider boundary never report success ---------------


def test_provider_error_is_failed_not_executed() -> None:
    sid = REGISTERED[0]
    adapters = {
        s: FakeAdapter(s, error=TimeoutError("slow") if s == sid else None) for s in REGISTERED
    }
    sources, _ = _sources(adapters=adapters)
    path, _ = _path(sources=sources)
    result = _run(path, sid)
    assert result.outcome is PathOutcome.FAILED and not result.executed
    assert result.reason == "provider-error:TimeoutError"
    assert result.steps[-1].name == "provider-call" and not result.steps[-1].passed


def test_invalid_adapter_result_is_failed() -> None:
    sid = REGISTERED[0]
    adapters = {s: FakeAdapter(s, result={"fake": 1} if s == sid else "ok") for s in REGISTERED}
    sources, _ = _sources(adapters=adapters)
    path, _ = _path(sources=sources)
    result = _run(path, sid)
    assert result.outcome is PathOutcome.FAILED and result.reason == "provider-invalid-result"


class _Cancelled:
    def raise_if_cancelled(self) -> None:
        raise RuntimeError("cancelled")


def test_cancellation_stops_before_the_provider_call() -> None:
    sid = REGISTERED[0]
    path, fakes = _path()
    result = _run(path, sid, request=_request(sid, cancellation=_Cancelled()))
    assert result.outcome is PathOutcome.FAILED and result.reason == "cancelled"
    assert all(len(f.calls) == 0 for f in fakes.values())


def test_path_result_is_never_executed_without_adapter_result() -> None:
    path, _ = _path()
    for sid in REGISTERED:
        result = _run(path, sid)
        assert result.executed == (result.adapter_result is not None)


def test_tool_contract_type_is_enforced_by_registry() -> None:
    assert all(isinstance(d.contract, ToolContract) for d in PROVIDER_TOOLS)
