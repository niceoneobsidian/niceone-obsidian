"""Tests for the governed read-only MCP adapter."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from ois.kernel.evidence import SQLiteEvidenceLedger
from ois.kernel.policy import DefaultPolicyEngine
from ois.mcp_server import ReadOnlyMCPService


def test_readiness_uses_spine_and_records_matching_execution_evidence(
    tmp_path: Path,
) -> None:
    service = ReadOnlyMCPService(tmp_path, tenant_id="test-local-vscode")
    try:
        result = service.readiness()
        assert result["status"] == "succeeded"
        assert result["output"] == {
            "service": "niceone-obsidian",
            "status": "ready",
            "mode": "read_only",
        }
        assert result["execution_id"]
        assert result["invocation_id"]
        assert result["evidence"]
        assert {
            event["event_type"] for event in result["evidence"]
        } >= {
            "spine.intent.accepted",
            "execution.authorized",
            "capability.completed",
            "execution.completed",
            "spine.verified",
        }
        assert all(
            event["execution_id"] == result["execution_id"]
            for event in result["evidence"]
        )
    finally:
        service.close()

    # Evidence must remain available after the service/store has been recreated.
    reopened = SQLiteEvidenceLedger(str(tmp_path / "evidence.sqlite3"))
    try:
        persisted = reopened.list()
        assert persisted
        assert {str(event.execution_id) for event in persisted} == {result["execution_id"]}
        assert "execution.completed" in {event.event_type for event in persisted}
    finally:
        reopened.close()


def test_readiness_reports_kernel_authorization_denial(tmp_path: Path) -> None:
    service = ReadOnlyMCPService(
        tmp_path,
        tenant_id="test-local-vscode",
        policy=DefaultPolicyEngine(),
    )
    try:
        result = service.readiness()
        assert result["status"] == "denied"
        assert result["error"] is not None
        assert any(
            event["event_type"] == "spine.authorization.denied"
            for event in result["evidence"]
        )
        assert not any(
            event["event_type"] == "capability.started"
            for event in result["evidence"]
        )
    finally:
        service.close()


def test_vscode_mcp_stdio_client_receives_real_ois_execution_receipt(
    tmp_path: Path,
) -> None:
    async def run_client() -> dict[str, Any]:
        repository_root = Path(__file__).resolve().parents[2]
        environment = os.environ.copy()
        environment["OIS_MCP_STATE_DIR"] = str(tmp_path)
        environment["OIS_MCP_TENANT_ID"] = "test-vscode-client"
        parameters = StdioServerParameters(
            command=sys.executable,
            args=["-m", "ois.mcp_server"],
            env=environment,
            cwd=str(repository_root),
        )
        async with stdio_client(parameters) as (read_stream, write_stream):
            async with ClientSession(read_stream, write_stream) as session:
                await session.initialize()
                tools = await session.list_tools()
                assert [tool.name for tool in tools.tools] == ["ois_readiness"]
                response = await session.call_tool("ois_readiness", arguments={})
                assert not getattr(response, "isError", False)

                structured = getattr(response, "structuredContent", None)
                if isinstance(structured, dict):
                    return structured
                for block in response.content:
                    if getattr(block, "type", None) == "text":
                        parsed = json.loads(block.text)
                        if isinstance(parsed, dict):
                            return parsed
                raise AssertionError("MCP tool response did not contain a JSON object")

    result = asyncio.run(run_client())
    assert result["status"] == "succeeded"
    assert result["output"]["mode"] == "read_only"
    assert result["execution_id"]
    assert result["evidence"]
    assert all(
        event["execution_id"] == result["execution_id"]
        for event in result["evidence"]
    )

    # The evidence receipt returned over MCP must match the durable ledger on disk.
    ledger = SQLiteEvidenceLedger(str(tmp_path / "evidence.sqlite3"))
    try:
        stored_events = ledger.list()
        assert stored_events
        assert {str(event.execution_id) for event in stored_events} == {
            result["execution_id"]
        }
        assert {event.event_type for event in stored_events} >= {
            "execution.authorized",
            "capability.completed",
            "execution.completed",
        }
    finally:
        ledger.close()
