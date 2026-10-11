"""Conformance tests for the governed REA MCP integration."""

from __future__ import annotations

from pathlib import Path
from collections.abc import Mapping
from typing import Any


from ois.integration.spine import OISSpine, SpineRequest
from ois.integrations.rea_mcp import (
    REA_ANALYZE_TOOL,
    REA_PERMISSION,
    REA_SESSION_TOOL,
    register_rea_tools,
)
from ois.kernel.checkpoint import SQLiteCheckpointStore
from ois.kernel.evidence import SQLiteEvidenceLedger
from ois.kernel.policy import DefaultPolicyEngine
from ois.registries.core import CapabilityRegistry, ToolRegistry


class FakeREAClient:
    def __init__(self, result: dict[str, Any] | None = None) -> None:
        self.result = result or {"normalized_result": {"status": "ok"}}
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def call_tool(self, name: str, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        self.calls.append((name, dict(arguments)))
        return self.result


def test_registers_only_allowlisted_rea_tools_in_both_registries(tmp_path: Path) -> None:
    roots = tmp_path / "targets"
    roots.mkdir()
    capabilities = CapabilityRegistry()
    tools = ToolRegistry()
    client = FakeREAClient()

    registered = register_rea_tools(
        capabilities,
        tools,
        allowed_roots=[roots],
        client=client,
    )

    assert {cap.contract.capability_id for cap in registered} == {
        "rea.binary_session",
        "rea.analyze_javascript_application",
    }
    for capability in registered:
        assert capabilities.has(capability.contract.capability_id, "1.0.0")
        assert tools.has(capability.contract.capability_id, "1.0.0")
        assert capabilities.get(capability.contract.capability_id, "1.0.0").contract == (
            tools.get(capability.contract.capability_id, "1.0.0").contract
        )
        assert capability.contract.permissions == (REA_PERMISSION,)


def test_static_analysis_flows_through_spine_policy_and_evidence(tmp_path: Path) -> None:
    roots = tmp_path / "targets"
    roots.mkdir()
    target = roots / "app"
    target.mkdir()
    (target / "main.js").write_text("console.log('static analysis only')", encoding="utf-8")
    client = FakeREAClient({"normalized_result": {"modules": 3, "coverage": "complete"}})
    capabilities = CapabilityRegistry()
    tools = ToolRegistry()
    register_rea_tools(capabilities, tools, allowed_roots=[roots], client=client)

    ledger_path = tmp_path / "evidence.sqlite3"
    checkpoints = SQLiteCheckpointStore(str(tmp_path / "checkpoints.sqlite3"))
    ledger = SQLiteEvidenceLedger(str(ledger_path))
    spine = OISSpine(
        capabilities,
        checkpoint_store=checkpoints,
        evidence=ledger,
        policy=DefaultPolicyEngine(allowed_permissions=(REA_PERMISSION,)),
    )
    try:
        result = spine.submit(
            SpineRequest(
                objective="Statically inspect an approved JavaScript application",
                capability_id="rea.analyze_javascript_application",
                capability_version="1.0.0",
                tenant_id="test-tenant",
                input={"input_path": str(target), "detail": "summary"},
            )
        )
        assert result.status == "succeeded"
        assert result.output == {
            "provider": "rea",
            "tool": REA_ANALYZE_TOOL,
            "result": {"normalized_result": {"modules": 3, "coverage": "complete"}},
        }
        assert client.calls == [
            (
                REA_ANALYZE_TOOL,
                {"input_path": str(target.resolve()), "detail": "summary"},
            )
        ]
        event_types = {str(event["event_type"]) for event in result.evidence}
        assert {
            "spine.intent.accepted",
            "execution.authorized",
            "capability.completed",
            "execution.completed",
            "spine.verified",
        } <= event_types
        assert all(str(event["execution_id"]) == result.execution_id for event in result.evidence)
    finally:
        ledger.close()
        checkpoints.close()


def test_path_escape_is_rejected_before_mcp_call(tmp_path: Path) -> None:
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    denied = tmp_path / "denied"
    denied.mkdir()
    (denied / "secret.js").write_text("not allowed", encoding="utf-8")
    client = FakeREAClient()
    capabilities = CapabilityRegistry()
    tools = ToolRegistry()
    register_rea_tools(capabilities, tools, allowed_roots=[allowed], client=client)

    ledger = SQLiteEvidenceLedger(str(tmp_path / "evidence.sqlite3"))
    checkpoints = SQLiteCheckpointStore(str(tmp_path / "checkpoints.sqlite3"))
    spine = OISSpine(
        capabilities,
        checkpoint_store=checkpoints,
        evidence=ledger,
        policy=DefaultPolicyEngine(allowed_permissions=(REA_PERMISSION,)),
    )
    try:
        result = spine.submit(
            SpineRequest(
                objective="Reject a target outside approved roots",
                capability_id="rea.analyze_javascript_application",
                capability_version="1.0.0",
                tenant_id="test-tenant",
                input={"input_path": str(denied / "secret.js"), "detail": "summary"},
            )
        )
        assert result.status == "failed"
        assert client.calls == []
        assert any(
            event["event_type"] == "execution.failure"
            for event in result.evidence
        )
    finally:
        ledger.close()
        checkpoints.close()


def test_policy_denial_prevents_rea_call(tmp_path: Path) -> None:
    roots = tmp_path / "targets"
    roots.mkdir()
    client = FakeREAClient()
    capabilities = CapabilityRegistry()
    tools = ToolRegistry()
    register_rea_tools(capabilities, tools, allowed_roots=[roots], client=client)

    ledger = SQLiteEvidenceLedger(str(tmp_path / "evidence.sqlite3"))
    checkpoints = SQLiteCheckpointStore(str(tmp_path / "checkpoints.sqlite3"))
    spine = OISSpine(
        capabilities,
        checkpoint_store=checkpoints,
        evidence=ledger,
        policy=DefaultPolicyEngine(),
    )
    try:
        result = spine.submit(
            SpineRequest(
                objective="Verify REA is blocked without its permission",
                capability_id="rea.binary_session",
                capability_version="1.0.0",
                tenant_id="test-tenant",
                input={},
            )
        )
        assert result.status == "denied"
        assert client.calls == []
        assert any(event["event_type"] == "spine.authorization.denied" for event in result.evidence)
    finally:
        ledger.close()
        checkpoints.close()


def test_rea_session_tool_is_fixed_and_takes_no_arguments(tmp_path: Path) -> None:
    roots = tmp_path / "targets"
    roots.mkdir()
    client = FakeREAClient({"tool_availability": {}})
    capabilities = CapabilityRegistry()
    tools = ToolRegistry()
    register_rea_tools(capabilities, tools, allowed_roots=[roots], client=client)

    ledger = SQLiteEvidenceLedger(str(tmp_path / "evidence.sqlite3"))
    checkpoints = SQLiteCheckpointStore(str(tmp_path / "checkpoints.sqlite3"))
    spine = OISSpine(
        capabilities,
        checkpoint_store=checkpoints,
        evidence=ledger,
        policy=DefaultPolicyEngine(allowed_permissions=(REA_PERMISSION,)),
    )
    try:
        result = spine.submit(
            SpineRequest(
                objective="Inspect REA MCP session status",
                capability_id="rea.binary_session",
                capability_version="1.0.0",
                tenant_id="test-tenant",
                input={},
            )
        )
        assert result.status == "succeeded"
        assert client.calls == [(REA_SESSION_TOOL, {})]
    finally:
        ledger.close()
        checkpoints.close()
