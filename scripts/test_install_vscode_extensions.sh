#!/usr/bin/env bash
# Lightweight contract test for install_vscode_extensions.sh; no network or VS Code required.

set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
installer="$script_dir/install_vscode_extensions.sh"

bash -n "$installer"

for extension in ms-python.python dbaeumer.vscode-eslint ms-vscode-remote.remote-containers supabase.supabase; do
  if ! rg -Fqx "  $extension" "$installer"; then
    printf 'Missing required extension: %s\n' "$extension" >&2
    exit 1
  fi
done

extension_count="$(sed -n '/^extensions=(/,/^)$/p' "$installer" | rg '^  [A-Za-z0-9.-]+$' | wc -l | tr -d ' ')"
if [[ "$extension_count" != "38" ]]; then
  printf 'Expected 38 extensions, found %s\n' "$extension_count" >&2
  exit 1
fi

printf 'VS Code extension installer contract test passed.\n'
