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

@dataclass(frozen=True)
class Check:
    name: str
    command: tuple[str, ...]
    required_tool: str

CHECKS = (
    Check("Ruff lint", ("ruff", "check", "."), "ruff"),
    Check("Ruff format", ("ruff", "format", "--check", "."), "ruff"),
    Check("Mypy", ("python", "-m", "mypy", "ois"), "mypy"),
    Check("Bandit", ("bandit", "-r", ".", "-x", "./.git,./.venv,./venv,./tests", "-lll", "-iii"), "bandit"),
    Check("Gitleaks", ("gitleaks", "detect", "--no-banner", "--redact"), "gitleaks"),
    Check("License compliance", ("pip-licenses", "--format=csv"), "pip-licenses"),
    Check("OIS governance", ("python", "scripts/ois_governance_check.py"), "python"),
    Check("Tests", ("python", "-m", "pytest", "-q"), "pytest"),
)


def executable(check: Check) -> str | None:
    if check.command[0] == "python":
        return sys.executable
    return shutil.which(check.required_tool)


def run_check(check: Check) -> tuple[str, int | None, str]:
    exe = executable(check)
    if exe is None:
        return "NOT_INSTALLED", None, "required executable is not installed"
    command = (exe, *check.command[1:]) if check.command[0] == "python" else check.command
    proc = subprocess.run(command, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=False)
    return ("PASS" if proc.returncode == 0 else "FAIL"), proc.returncode, proc.stdout.strip()


def main() -> int:
    print("OIS LOCAL CI")
    print("=" * 60)
    results: list[tuple[Check, str]] = []
    for check in CHECKS:
        state, code, output = run_check(check)
        results.append((check, state))
        print(f"{check.name:<24} {state}")
        if state in {"FAIL", "NOT_INSTALLED"} and output:
            print("  " + output.replace("\n", "\n  ")[:1200])
    print("=" * 60)
    failures = [c.name for c, s in results if s in {"FAIL", "NOT_INSTALLED"}]
    overall = "PASS" if not failures else "FAIL"
    print(f"RESULT: {overall}")
    return 0 if overall == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
