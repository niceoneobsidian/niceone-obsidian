# REA MCP integration

REA is registered as a governed OIS MCP provider, not as a second execution
kernel. The adapter uses the canonical **CapabilityRegistry**, **ToolRegistry**,
**OISSpine**, Kernel policy/validation, checkpointing, and Evidence Ledger.

## Registered operations

| OIS capability | REA MCP tool | Purpose |
|---|---|---|
| rea.binary_session@1.0.0 | binary_session | Read current REA session/provider availability |
| rea.analyze_javascript_application@1.0.0 | analyze_javascript_application | Static JavaScript/Electron application analysis |

This is an intentionally narrow allowlist. It does **not** expose arbitrary
tools/call, native binary operations, process capture, browser interaction,
evidence-bundle export, or other REA tools. Add an operation only with a typed
contract, explicit risk/side-effect classification, authorization tests, and
provider-specific conformance coverage.

## Execution and isolation boundary

REA's MCP server runs as a local process and can inspect files available to that
process. Therefore REAStdioMCPClient calls the repository's existing
production.sandbox.attest() before launching npx. The launch fails closed unless
the current worker passes the gVisor runtime and privilege-restriction checks.
The REA analysis target must also resolve inside an explicitly configured
allowlisted root; symlink-resolved paths outside those roots are rejected before
MCP invocation.

Path allowlisting is defense in depth, **not** a replacement for OS isolation.
Run this adapter only in the OIS gVisor worker boundary. The first registered
analysis operation is REA's static JavaScript/Electron analysis, which documents
that it does not execute the target application. Runtime capture and native
analysis tools remain unregistered.

## Configuration

Install the optional MCP dependency and ensure Node.js/npm (npx) is available
inside the isolated worker:

    python -m pip install -e '.[mcp]'

The adapter launches a pinned package without a shell:

    npx --yes rea-agents@6.4.0 mcp

The target roots are supplied by trusted application configuration, not by an
MCP caller. Example registration:

    from pathlib import Path

    from ois.integrations.rea_mcp import register_rea_tools
    from ois.registries.core import CapabilityRegistry, ToolRegistry

    capabilities = CapabilityRegistry()
    tools = ToolRegistry()
    register_rea_tools(
        capabilities,
        tools,
        allowed_roots=[Path("/workspace/reverse-engineering/targets")],
    )

The application then submits the selected capability through OISSpine.submit()
with the existing policy granting reverse_engineering.read only to authorized
principals. Do not grant that permission globally merely to make discovery work.

For static analysis, the input is exactly:

    {
      "input_path": "/workspace/reverse-engineering/targets/example-app",
      "detail": "summary"
    }

The detail value may be summary or complete. Paths must be absolute, exist, and
resolve to a file or directory under an approved root. The adapter rejects extra
input keys and does not accept caller-supplied REA tool names, process commands,
tenant IDs, or MCP server arguments.

## Evidence and verification

The OIS Kernel records authorization, capability lifecycle, checkpoint, and
execution evidence through the configured Evidence Ledger. The REA result is
retained as the capability output, including its provider-native evidence and
coverage/limitation fields. OIS completion evidence means the governed invocation
completed; it does not independently certify that REA's reverse-engineering
conclusion is correct.

The conformance tests use an injected fake MCP client and verify:

- registration in both canonical registries with matching contracts;
- successful invocation through OIS policy, runtime, checkpoint, and evidence;
- denial without reverse_engineering.read;
- rejection of a target outside configured roots before any MCP call; and
- fixed tool names and exact input keys.

These tests do not claim that a real REA package, Node.js runtime, native provider,
or gVisor deployment has been exercised. A live smoke test must run on the actual
gVisor worker with the pinned REA package available.
