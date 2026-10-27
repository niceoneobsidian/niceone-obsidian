"""Conformance tests for the governed REA MCP integration."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
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


def _setup(
    tmp_path: Path,
    roots: list[Path],
    client: FakeREAClient,
    *,
    permissions: tuple[str, ...] = (REA_PERMISSION,),
) -> tuple[CapabilityRegistry, ToolRegistry, SQLiteEvidenceLedger, SQLiteCheckpointStore, OISSpine]:
    capabilities = CapabilityRegistry()
    tools = ToolRegistry()
    ledger = SQLiteEvidenceLedger(str(tmp_path / "evidence.sqlite3"))
    checkpoints = SQLiteCheckpointStore(str(tmp_path / "checkpoints.sqlite3"))
    register_rea_tools(
        capabilities,
        tools,
        allowed_roots=roots,
        client=client,
        evidence=ledger,
    )
    spine = OISSpine(
        capabilities,
        checkpoint_store=checkpoints,
        evidence=ledger,
        policy=DefaultPolicyEngine(allowed_permissions=permissions),
    )
    return capabilities, tools, ledger, checkpoints, spine


def test_registers_only_allowlisted_rea_tools_in_both_registries(tmp_path: Path) -> None:
    roots = tmp_path / "targets"
    roots.mkdir()
    client = FakeREAClient()
    capabilities, tools, ledger, checkpoints, _ = _setup(tmp_path, [roots], client)
    try:
        expected = {"rea.binary_session", "rea.analyze_javascript_application"}
        assert {entry.id for entry in capabilities.snapshot()} == expected
        assert {entry.id for entry in tools.snapshot()} == expected
        for capability_id in expected:
            capability_entry = capabilities.get(capability_id, "1.0.0")
            tool_entry = tools.get(capability_id, "1.0.0")
            assert capability_entry.contract == tool_entry.contract
            assert capability_entry.contract.permissions == (REA_PERMISSION,)
    finally:
        ledger.close()
        checkpoints.close()


def test_static_analysis_flows_through_spine_policy_and_evidence(tmp_path: Path) -> None:
    roots = tmp_path / "targets"
    roots.mkdir()
    target = roots / "app"
    target.mkdir()
    (target / "main.js").write_text("console.log('static analysis only')", encoding="utf-8")
    client = FakeREAClient(
        {
            "normalized_result": {
                "modules": 3,
                "coverage": "complete",
                "evidence_id": "ev_123",
            }
        }
    )
    _, _, ledger, checkpoints, spine = _setup(tmp_path, [roots], client)
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
            "result": {
                "normalized_result": {
                    "modules": 3,
                    "coverage": "complete",
                    "evidence_id": "ev_123",
                }
            },
        }
        assert client.calls == [
            (REA_ANALYZE_TOOL, {"input_path": str(target.resolve()), "detail": "summary"})
        ]
        event_types = {str(event["event_type"]) for event in result.evidence}
        assert {
            "spine.intent.accepted",
            "execution.authorized",
            "rea.mcp.result_received",
            "capability.completed",
            "execution.completed",
            "spine.verified",
        } <= event_types
        receipt = next(
            event for event in result.evidence if event["event_type"] == "rea.mcp.result_received"
        )
        assert len(receipt["data"]["result_sha256"]) == 64
        assert receipt["data"]["evidence_ids"] == ["ev_123"]
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
    _, _, ledger, checkpoints, spine = _setup(tmp_path, [allowed], client)
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
        assert any(event["event_type"] == "execution.failure" for event in result.evidence)
        assert not any(
            event["event_type"] == "rea.mcp.result_received" for event in result.evidence
        )
    finally:
        ledger.close()
        checkpoints.close()


def test_policy_denial_prevents_rea_call(tmp_path: Path) -> None:
    roots = tmp_path / "targets"
    roots.mkdir()
    client = FakeREAClient()
    _, _, ledger, checkpoints, spine = _setup(tmp_path, [roots], client, permissions=())
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
    _, _, ledger, checkpoints, spine = _setup(tmp_path, [roots], client)
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
        assert any(event["event_type"] == "rea.mcp.result_received" for event in result.evidence)
    finally:
        ledger.close()
        checkpoints.close()
