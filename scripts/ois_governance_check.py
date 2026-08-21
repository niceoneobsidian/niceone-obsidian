"""Free-tier OIS governance gate.

This is a deterministic CI/local control, not server-side branch protection.
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_MARKERS = ("branch protection test", "branch protection enforcement test")


def run(*args: str) -> tuple[int, str]:
    result = subprocess.run(
        args,
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    return result.returncode, result.stdout


def main() -> int:
    failures: list[str] = []
    code, branch = run("git", "branch", "--show-current")
    branch = branch.strip()
    if code != 0:
        failures.append("unable to determine current Git branch")
    elif branch == "main" and not os.environ.get("OIS_ALLOW_MAIN"):
        failures.append("governance check must run from a PR/development branch")

    code, status = run("git", "status", "--porcelain")
    if code != 0:
        failures.append("unable to inspect Git working tree")
    elif status.strip():
        failures.append("working tree is not clean")

    code, _ = run("git", "diff", "--check")
    if code != 0:
        failures.append("git diff --check failed")

    readme = (ROOT / "README.md").read_text(encoding="utf-8").lower()
    for marker in FORBIDDEN_MARKERS:
        if marker in readme:
            failures.append(f"forbidden test marker remains in README.md: {marker}")

    if failures:
        print("OIS GOVERNANCE GATE: FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("OIS GOVERNANCE GATE: PASS")
    print("- development/PR branch")
    print("- clean working tree")
    print("- no diff whitespace errors")
    print("- no branch-protection test markers in README.md")
    print("- server-side GitHub branch protection remains separately classified")
    return 0


if __name__ == "__main__":
    sys.exit(main())
