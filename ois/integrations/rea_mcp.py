"""Governed, read-only integration with the REA MCP server.

Only the explicitly registered REA tools are callable. Local analysis targets are
canonicalized and constrained to administrator-configured roots before crossing
the MCP boundary. Invocation remains inside the OIS Kernel lifecycle.
"""

from __future__ import annotations

import asyncio
import json
import os
import shutil
from collections.abc import Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Protocol

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from ois.kernel.contracts import InvocationRequest, InvocationResult, ToolContract
from ois.kernel.types import InvocationStatus, RiskLevel, SideEffectLevel
from ois.registries.core import CapabilityRegistry, ToolRegistry

REA_PACKAGE = "rea-agents@6.4.0"
REA_ANALYZE_TOOL = "analyze_javascript_application"
REA_SESSION_TOOL = "binary_session"
REA_PERMISSION = "reverse_engineering.read"
REA_TIMEOUT_SECONDS = 300.0


class REAMCPClient(Protocol):
    """Minimal client interface, injectable for tests and alternate transports."""

    def call_tool(self, name: str, arguments: Mapping[str, Any]) -> Mapping[str, Any]: ...


class REAStdioMCPClient:
    """One-request stdio MCP client for the pinned REA package.

    The server command is fixed (no shell and no caller-provided command vector).
    Only a small environment allowlist is inherited by the REA process.
    """

    _ENV_KEYS = (
        "PATH",
        "HOME",
        "TMPDIR",
        "TMP",
        "TEMP",
        "SYSTEMROOT",
        "APPDATA",
        "LOCALAPPDATA",
        "USERPROFILE",
    )

    def __init__(self, *, timeout_seconds: float = REA_TIMEOUT_SECONDS) -> None:
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        self.timeout_seconds = timeout_seconds

    def call_tool(self, name: str, arguments: Mapping[str, Any]) -> Mapping[str, Any]:
        if name not in {REA_SESSION_TOOL, REA_ANALYZE_TOOL}:
            raise ValueError(f"REA tool is not allowlisted: {name}")
        coroutine = self._call_tool(name, dict(arguments))
        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(coroutine)

        # OIS capability invocation is synchronous. If called from an async host,
        # keep the MCP event loop isolated on a dedicated worker thread.
        with ThreadPoolExecutor(max_workers=1, thread_name_prefix="rea-mcp") as pool:
            return pool.submit(asyncio.run, coroutine).result(timeout=self.timeout_seconds + 5)

    async def _call_tool(self, name: str, arguments: dict[str, Any]) -> Mapping[str, Any]:
        executable = shutil.which("npx")
        if executable is None:
            raise RuntimeError("REA MCP requires Node.js/npm with npx available on PATH")

        environment = {key: os.environ[key] for key in self._ENV_KEYS if key in os.environ}
        parameters = StdioServerParameters(
            command=executable,
            args=["--yes", REA_PACKAGE, "mcp"],
            env=environment,
        )
        async with asyncio.timeout(self.timeout_seconds):
            async with (
                stdio_client(parameters) as (read_stream, write_stream),
                ClientSession(read_stream, write_stream) as session,
            ):
                await session.initialize()
                catalog = await session.list_tools()
                if name not in {tool.name for tool in catalog.tools}:
                    raise RuntimeError(f"REA server does not advertise required tool: {name}")
                result = await session.call_tool(name, arguments=dict(arguments))
                if getattr(result, "isError", False):
                    raise RuntimeError(_tool_error_text(result))
                structured = getattr(result, "structuredContent", None)
                if isinstance(structured, Mapping):
                    return dict(structured)
                for block in getattr(result, "content", ()):
                    if getattr(block, "type", None) == "text":
                        try:
                            parsed = json.loads(block.text)
                        except (TypeError, json.JSONDecodeError):
                            continue
                        if isinstance(parsed, Mapping):
                            return dict(parsed)
                raise RuntimeError("REA returned no structured JSON tool result")


def _tool_error_text(result: Any) -> str:
    """Extract bounded, useful MCP error detail without dumping arbitrary payloads."""
    for block in getattr(result, "content", ()):
        if getattr(block, "type", None) == "text":
            text = str(getattr(block, "text", ""))
            if text:
                return text[:2000]
    return "REA MCP tool returned isError=true"


def _inside_allowed_root(target: Path, roots: Sequence[Path]) -> Path:
    if not target.is_absolute():
        raise ValueError("input_path must be absolute")
    resolved = target.resolve(strict=True)
    if not any(resolved == root or root in resolved.parents for root in roots):
        raise PermissionError("input_path is outside configured REA analysis roots")
    if not (resolved.is_file() or resolved.is_dir()):
        raise ValueError("input_path must resolve to a file or directory")
    return resolved


class REAToolCapability:
    """Adapt one fixed REA MCP operation to the canonical OIS capability contract."""

    def __init__(
        self,
        *,
        tool_name: str,
        capability_id: str,
        client: REAMCPClient,
        allowed_roots: Sequence[Path],
    ) -> None:
        if tool_name not in {REA_SESSION_TOOL, REA_ANALYZE_TOOL}:
            raise ValueError(f"REA tool is not allowlisted: {tool_name}")
        roots = tuple(root.resolve(strict=True) for root in allowed_roots)
        if not roots or any(not root.is_dir() for root in roots):
            raise ValueError("at least one existing REA analysis root directory is required")
        self.tool_name = tool_name
        self.client = client
        self.allowed_roots = roots
        if tool_name == REA_SESSION_TOOL:
            input_schema: Mapping[str, Any] = {"type": "object"}
            required: tuple[str, ...] = ()
            description = "Read REA MCP session/provider readiness without opening a target."
        else:
            input_schema = {
                "type": "object",
                "required": ["input_path", "detail"],
                "properties": {
                    "input_path": {"type": "string"},
                    "detail": {"type": "string", "enum": ["summary", "complete"]},
                },
            }
            required = ("input_path", "detail")
            description = (
                "Statically analyze a local JavaScript/Electron application through REA. "
                "Target paths must remain inside configured analysis roots; this operation "
                "does not execute the target application."
            )
        self.contract = ToolContract(
            capability_id=capability_id,
            version="1.0.0",
            description=description,
            input_schema=input_schema,
            output_schema={
                "type": "object",
                "required": ["provider", "tool", "result"],
                "properties": {
                    "provider": {"type": "string", "enum": ["rea"]},
                    "tool": {"type": "string", "enum": [tool_name]},
                    "result": {"type": "object"},
                },
            },
            risk_level=RiskLevel.MEDIUM,
            permissions=(REA_PERMISSION,),
            allowed_domains=("local-analysis",),
            timeout_seconds=REA_TIMEOUT_SECONDS,
            max_retries=0,
            side_effects=SideEffectLevel.NONE,
            idempotent=True,
            network_policy={
                "transport": "stdio",
                "package": REA_PACKAGE,
                "allowed_tools": [REA_SESSION_TOOL, REA_ANALYZE_TOOL],
                "target_execution": False,
            },
            secrets_required=(),
            requires_approval=False,
        )
        self._required = required

    def invoke(self, request: InvocationRequest) -> InvocationResult:
        arguments = dict(request.input)
        if set(arguments) != set(self._required):
            raise ValueError(
                "REA capability accepts exactly these input keys: "
                + ", ".join(self._required)
            )
        if self.tool_name == REA_ANALYZE_TOOL:
            resolved = _inside_allowed_root(Path(str(arguments["input_path"])), self.allowed_roots)
            arguments["input_path"] = str(resolved)

        result = self.client.call_tool(self.tool_name, arguments)
        return InvocationResult(
            invocation_id=request.invocation_id,
            capability_id=self.contract.capability_id,
            status=InvocationStatus.SUCCEEDED,
            output={"provider": "rea", "tool": self.tool_name, "result": dict(result)},
            metadata={"mcp_tool": self.tool_name, "mcp_package": REA_PACKAGE},
        )


def register_rea_tools(
    capability_registry: CapabilityRegistry,
    tool_registry: ToolRegistry,
    *,
    allowed_roots: Sequence[str | Path],
    client: REAMCPClient | None = None,
) -> tuple[REAToolCapability, ...]:
    """Register the small, read-only REA allowlist in both canonical registries.

    This function intentionally does not register every tool advertised by REA.
    Expand the allowlist only alongside explicit contracts, path/risk policy and
    conformance tests for each additional operation.
    """
    roots = tuple(Path(root).expanduser() for root in allowed_roots)
    transport = client or REAStdioMCPClient()
    definitions = (
        (REA_SESSION_TOOL, "rea.binary_session"),
        (REA_ANALYZE_TOOL, "rea.analyze_javascript_application"),
    )
    capabilities = tuple(
        REAToolCapability(
            tool_name=tool_name,
            capability_id=capability_id,
            client=transport,
            allowed_roots=tuple(root.resolve(strict=True) for root in roots),
        )
        for tool_name, capability_id in definitions
    )
    for capability in capabilities:
        capability_registry.register(capability)
        tool_registry.register(
            capability,
            metadata={
                "provider": "rea",
                "mcp_tool": capability.tool_name,
                "authority": "OIS Kernel policy and execution spine",
                "side_effects": "none",
            },
        )
    return capabilities
