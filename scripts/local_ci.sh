#!/usr/bin/env bash

set -uo pipefail

RUFF_LINT_RC=1
RUFF_FORMAT_RC=1
MYPY_RC=1
BANDIT_RC=1
GOVERNANCE_RC=1
PYTEST_RC=1

echo "=== Ruff lint ==="
python -m ruff check .
RUFF_LINT_RC=$?

echo
echo "=== Ruff format ==="
python -m ruff format --check .
RUFF_FORMAT_RC=$?

echo
echo "=== Mypy ==="
python -m mypy ois ops production
MYPY_RC=$?

echo
echo "=== Bandit ==="
python -m bandit -r ois scripts   -x ./.git,./.venv,./venv,./tests   -lll -iii
BANDIT_RC=$?

echo
echo "=== Governance ==="
python scripts/validate_phase_gates.py
GOVERNANCE_RC=$?

echo
echo "=== Tests ==="
python -m pytest -q
PYTEST_RC=$?

echo
echo "=== Results ==="
printf 'RUFF_LINT=%s RUFF_FORMAT=%s MYPY=%s BANDIT=%s GOVERNANCE=%s PYTEST=%s\n'   "$RUFF_LINT_RC"   "$RUFF_FORMAT_RC"   "$MYPY_RC"   "$BANDIT_RC"   "$GOVERNANCE_RC"   "$PYTEST_RC"

if [ "$RUFF_LINT_RC" -ne 0 ]   || [ "$RUFF_FORMAT_RC" -ne 0 ]   || [ "$MYPY_RC" -ne 0 ]   || [ "$BANDIT_RC" -ne 0 ]   || [ "$GOVERNANCE_RC" -ne 0 ]   || [ "$PYTEST_RC" -ne 0 ]; then
  echo
  echo "Local CI failed."
  exit 1
fi

echo
echo "Local CI passed."
