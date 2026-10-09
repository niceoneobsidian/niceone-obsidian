"""VS Code MCP adapter for a fixed, read-only OIS Kernel probe.

The MCP boundary accepts no capability identifier, tenant, or arbitrary input from
the client. It submits one fixed request through OISSpine so the existing Kernel
contract validation, policy authorization, checkpointing, and evidence path remain
authoritative.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from ois.integration.spine import OISSpine, SpineRequest
from ois.kernel.checkpoint import SQLiteCheckpointStore
from ois.kernel.contracts import CapabilityContract, InvocationRequest, InvocationResult
from ois.kernel.evidence import SQLiteEvidenceLedger
from ois.kernel.policy import DefaultPolicyEngine, PolicyEngine
from ois.kernel.types import InvocationStatus, RiskLevel, SideEffectLevel
from ois.registries import CapabilityRegistry

CAPABILITY_ID = "ois.mcp.readiness"
CAPABILITY_VERSION = "1.0.0"
READ_PERMISSION = "execution.read"


class ReadOnlyProbeCapability:
    """Deterministic, no-side-effect capability used to verify the governed path."""

    contract = CapabilityContract(
        capability_id=CAPABILITY_ID,
        version=CAPABILITY_VERSION,
        description="Verify that the governed OIS execution path is available.",
        input_schema={"type": "object"},
        output_schema={
            "type": "object",
            "required": ["service", "status", "mode"],
            "properties": {
                "service": {"type": "string"},
                "status": {"type": "string", "enum": ["ready"]},
                "mode": {"type": "string", "enum": ["read_only"]},
            },
        },
        risk_level=RiskLevel.LOW,
        permissions=(READ_PERMISSION,),
        side_effects=SideEffectLevel.NONE,
        idempotent=True,
    )

    def invoke(self, request: InvocationRequest) -> InvocationResult:
        output = {
            "service": "niceone-obsidian",
            "status": "ready",
            "mode": "read_only",
        }
        return InvocationResult(
            invocation_id=request.invocation_id,
            capability_id=self.contract.capability_id,
            status=InvocationStatus.SUCCEEDED,
            output=output,
        )


class ReadOnlyMCPService:
    """Own the durable stores and submit the fixed readiness request through OIS."""

    def __init__(
        self,
        state_dir: str | Path,
        *,
        tenant_id: str,
        policy: PolicyEngine | None = None,
    ) -> None:
        if not tenant_id or tenant_id != tenant_id.strip():
            raise ValueError("tenant_id must be a non-empty, trimmed trusted value")

        self.state_dir = Path(state_dir).expanduser()
        self.state_dir.mkdir(mode=0o700, parents=True, exist_ok=True)
        try:
            self.state_dir.chmod(0o700)
        except OSError:
            # Some filesystems do not support POSIX permissions; SQLite remains local.
            pass

        checkpoint_path = self.state_dir / "checkpoints.sqlite3"
        evidence_path = self.state_dir / "evidence.sqlite3"
        self.checkpoints = SQLiteCheckpointStore(str(checkpoint_path))
        self.evidence = SQLiteEvidenceLedger(str(evidence_path))
        for database_path in (checkpoint_path, evidence_path):
            try:
                database_path.chmod(0o600)
            except OSError:
                pass

        registry = CapabilityRegistry()
        registry.register(ReadOnlyProbeCapability())
        self.tenant_id = tenant_id
        self.spine = OISSpine(
            registry,
            checkpoint_store=self.checkpoints,
            evidence=self.evidence,
            policy=policy
            or DefaultPolicyEngine(allowed_permissions=(READ_PERMISSION,)),
        )

    def readiness(self) -> dict[str, Any]:
        """Execute the fixed read-only probe and return its real execution receipt."""
        result = self.spine.submit(
            SpineRequest(
                objective="Verify the governed OIS read-only MCP execution path",
                capability_id=CAPABILITY_ID,
                capability_version=CAPABILITY_VERSION,
                input={},
                tenant_id=self.tenant_id,
                workflow_id="ois.vscode.mcp",
                workflow_version="1.0",
            )
        )
        events = [
            {
                "event_id": str(event["event_id"]),
                "execution_id": str(event["execution_id"]),
                "event_type": str(event["event_type"]),
                "timestamp": str(event["timestamp"]),
            }
            for event in result.evidence
        ]
        return {
            "status": result.status,
            "execution_id": result.execution_id,
            "invocation_id": result.invocation_id,
            "output": result.output,
            "error": dict(result.error) if result.error is not None else None,
            "evidence": events,
        }

    def close(self) -> None:
        self.evidence.close()
        self.checkpoints.close()


def create_server(service: ReadOnlyMCPService) -> FastMCP:
    """Build an MCP server exposing only the fixed readiness operation."""
    server = FastMCP("OIS Governed Read-only")

    @server.tool(
        name="ois_readiness",
        description=(
            "Run a fixed, read-only readiness probe through the governed OIS Kernel. "
            "Returns the actual execution ID and evidence event receipt. Takes no arguments."
        ),
        structured_output=True,
    )
    def ois_readiness() -> dict[str, Any]:
        return service.readiness()

    return server


def main() -> None:
    """Start the stdio MCP server for a local VS Code client."""
    state_dir = Path(
        os.environ.get("OIS_MCP_STATE_DIR", str(Path.home() / ".ois" / "mcp"))
    )
    tenant_id = os.environ.get("OIS_MCP_TENANT_ID", "local-vscode")
    service = ReadOnlyMCPService(state_dir, tenant_id=tenant_id)
    try:
        create_server(service).run("stdio")
    finally:
        service.close()


if __name__ == "__main__":
    main()
