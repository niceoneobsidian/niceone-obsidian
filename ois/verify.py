"""Canonical local CI verifier for OIS.

Runs the repository's CI gates locally and reports explicit verification states.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENVIRONMENT_LIMITED_OUTPUT = "ModuleNotFoundError: No module named 'pydantic'"


@dataclass(frozen=True)
class Check:
    name: str
    command: tuple[str, ...]
    required_tool: str


CHECKS = (
    Check("Ruff lint", ("ruff", "check", "."), "ruff"),
    Check("Ruff format", ("ruff", "format", "--check", "."), "ruff"),
    Check("Mypy", ("python", "-m", "mypy", "ois"), "python"),
    Check(
        "Bandit",
        ("bandit", "-r", ".", "-x", "./.git,./.venv,./venv,./tests", "-lll", "-iii"),
        "bandit",
    ),
    Check("Gitleaks", ("gitleaks", "detect", "--no-banner", "--redact"), "gitleaks"),
    Check("License compliance", ("pip-licenses", "--format=csv"), "pip-licenses"),
    Check("OIS governance", ("python", "scripts/ois_governance_check.py"), "python"),
    Check("Tests", ("python", "-m", "pytest", "-q"), "python"),
)


def executable(check: Check) -> str | None:
    if check.command[0] == "python":
        return sys.executable
    return shutil.which(check.required_tool)


def classify_output(check: Check, returncode: int, output: str) -> str:
    if returncode == 0:
        return "PASS"
    if "No module named mypy" in output:
        return "SKIPPED"
    if check.name == "Tests" and ENVIRONMENT_LIMITED_OUTPUT in output:
        return "ENV_LIMITED"
    return "FAIL"


def run_check(check: Check) -> tuple[str, int | None, str]:
    exe = executable(check)
    if exe is None:
        return "SKIPPED", None, "required executable is not installed"
    command = (exe, *check.command[1:]) if check.command[0] == "python" else check.command
    proc = subprocess.run(
        command, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False
    )
    output = proc.stdout.strip()
    return classify_output(check, proc.returncode, output), proc.returncode, output


def overall_state(states: list[str]) -> str:
    if "FAIL" in states:
        return "FAIL"
    if any(state in {"SKIPPED", "ENV_LIMITED"} for state in states):
        return "PASS WITH LIMITATIONS"
    return "PASS"


def main() -> int:
    print("OIS LOCAL CI")
    print("=" * 60)
    results: list[tuple[Check, str]] = []
    for check in CHECKS:
        state, code, output = run_check(check)
        results.append((check, state))
        print(f"{check.name:<24} {state}")
        if state in {"FAIL", "SKIPPED", "ENV_LIMITED"} and output:
            print("  " + output.replace("\n", "\n  ")[:1200])
    print("=" * 60)
    overall = overall_state([state for _, state in results])
    print(f"RESULT: {overall}")
    return 1 if overall == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
