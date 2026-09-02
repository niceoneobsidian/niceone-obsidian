#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
INSTALLER="$SCRIPT_DIR/install_vscode_extensions.sh"

if [[ ! -f "$INSTALLER" ]]; then
    printf "Error: Target installer script not found at %s\n" "$INSTALLER" >&2
    exit 1
fi

printf "Validating script syntax...\n"
bash -n "$INSTALLER"

printf "Checking for required extensions...\n"
REQUIRED_EXTENSIONS=(
    "ms-python.python"
    "dbaeumer.vscode-eslint"
    "ms-vscode-remote.remote-containers"
    "supabase.supabase"
)

for extension in "${REQUIRED_EXTENSIONS[@]}"; do
    if ! rg -Fqx "$extension" "$INSTALLER"; then
        printf "Missing required extension: %s\n" "$extension" >&2
        exit 1
    fi
done

printf "Verifying total extension allocation...\n"
EXTENSION_COUNT=$(sed -n '/^extensions=(/,/^)$/p' "$INSTALLER" | rg '^[[:space:]]*[A-Za-z0-9.-]+$' | wc -l | tr -d ' ')

if [[ "$EXTENSION_COUNT" != "38" ]]; then
    printf "Expected 38 extensions, found %s\n" "$EXTENSION_COUNT" >&2
    exit 1
fi

printf "Success: VS Code extension installer contract test passed.\n"
