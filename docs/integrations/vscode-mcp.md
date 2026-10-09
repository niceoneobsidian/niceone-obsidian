# VS Code MCP integration

This integration exposes one fixed, read-only probe through the existing OIS execution spine.
The MCP client cannot choose a capability, supply arbitrary input, or override the tenant identity.

## Install the optional MCP dependency

From the repository root:

```bash
./.venv/bin/python -m pip install -e '.[mcp]'
```

## Configure VS Code

Create `.vscode/mcp.json` locally (the `.vscode/` directory is git-ignored):

```json
{
  "servers": {
    "ois-local": {
      "type": "stdio",
      "command": "${workspaceFolder}/.venv/bin/python",
      "args": ["-m", "ois.mcp_server"],
      "env": {
        "PYTHONPATH": "${workspaceFolder}",
        "OIS_MCP_TENANT_ID": "local-vscode"
      }
    }
  }
}
```

Restart or start the `ois-local` MCP server in VS Code. The available tool is
`ois_readiness`; it accepts no arguments. Its result includes the OIS execution ID,
invocation ID, result status, and evidence-event receipt.

## State and trust boundary

By default, SQLite checkpoints and evidence are stored under `~/.ois/mcp/`. Override the
directory with `OIS_MCP_STATE_DIR` when running the server in a test or isolated environment.
The server uses restrictive permissions for the state directory and database files where the
filesystem supports them.

`OIS_MCP_TENANT_ID` is read from the local server process environment, never from MCP tool
arguments. Configure it only from trusted local settings. The probe requires the
`execution.read` permission, and the local server's explicit policy grants that permission to
this fixed probe. All requests still pass through `OISSpine` and the Kernel validator,
authorization, checkpoint, and evidence lifecycle.

This first tool verifies the governed integration path; it is not a comprehensive health check
of external providers, PostgreSQL, Redis, or Ollama. Do not expose this local stdio server to
untrusted users or replace the fixed tool with arbitrary capability dispatch.
