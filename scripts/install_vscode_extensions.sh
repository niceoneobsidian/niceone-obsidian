#!/usr/bin/env bash
# Install the team's recommended Visual Studio Code extensions.
# Usage: ./scripts/install_vscode_extensions.sh
# Set VSCODE_BIN to use another compatible CLI (for example, `code-insiders`).

set -euo pipefail

VSCODE_BIN="${VSCODE_BIN:-code}"

extensions=(
  ms-python.python
  ms-python.vscode-pylance
  charliermarsh.ruff
  ms-python.debugpy
  ms-toolsai.jupyter
  dbaeumer.vscode-eslint
  esbenp.prettier-vscode
  bradlc.vscode-tailwindcss
  eamodio.gitlens
  GitHub.vscode-pull-request-github
  mhutchie.git-graph
  ms-azuretools.vscode-docker
  ms-vscode-remote.remote-containers
  mtxr.sqltools
  mtxr.sqltools-driver-pg
  supabase.supabase
  humao.rest-client
  redhat.vscode-yaml
  tamasfe.even-better-toml
  mikestead.dotenv
  usernamehw.errorlens
  gruntfuggly.todo-tree
  christian-kohler.path-intellisense
  EditorConfig.EditorConfig
  yzhang.markdown-all-in-one
  bierner.markdown-mermaid
  ms-python.mypy-type-checker
  littlefoxteam.vscode-python-test-adapter
  ryanluker.vscode-coverage-gutters
  github.vscode-github-actions
  timonwong.shellcheck
  SonarSource.sonarlint-vscode
  GitGuardian.gitguardian
  snyk-security.snyk-vulnerability-scanner
  christian-kohler.npm-intellisense
  pflannery.vscode-versionlens
  figma.figma-vscode-extension
  alefragnani.project-manager
)

if ! command -v "$VSCODE_BIN" >/dev/null 2>&1; then
  printf 'Could not find the VS Code CLI: %s\n' "$VSCODE_BIN" >&2
  printf "In VS Code, run ‘Shell Command: Install 'code' command in PATH’, then retry.\n" >&2
  exit 1
fi

printf 'Installing %d VS Code extensions using %s...\n' "${#extensions[@]}" "$VSCODE_BIN"
for extension in "${extensions[@]}"; do
  printf 'Installing %s\n' "$extension"
  "$VSCODE_BIN" --install-extension "$extension" --force
done

printf 'Done. Installed or updated %d extensions.\n' "${#extensions[@]}"
