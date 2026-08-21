"""Free-tier OIS governance gate.

This is an advisory/CI gate, not server-side branch protection. It makes the
repository's validation policy executable and auditable without claiming that
GitHub enforces protected-branch rules on the current plan.
"""
from __future__ import annotations

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
    elif branch == "main" and (ROOT / ".git").exists():
        # Direct local execution on main is blocked unless explicitly overridden.
        if "OIS_ALLOW_MAIN" not in __import__("os").environ:
            failures.append("governance check may not be run for a mutation on main; use a PR branch")

    code, status = run("git", "status", "--porcelain")
    if code != 0:
        failures.append("unable to inspect Git working tree")
    elif status.strip():
        failures.append("working tree is not clean")

    code, diff = run("git", "diff", "--check")
    if code != 0:
        failures.append("git diff --check failed")

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    lowered = readme.lower()
    for marker in FORBIDDEN_MARKERS:
        if marker in lowered:
            failures.append(f"forbidden test marker remains in README.md: {marker}")

    if failures:
        print("OIS GOVERNANCE GATE: FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1

    print("OIS GOVERNANCE GATE: PASS")
    print("- clean working tree")
    print("- no diff whitespace errors")
    print("- no archived branch-protection test markers in README.md")
    print("- repository policy is advisory/CI-enforced; GitHub server-side rules remain plan-dependent")
    return 0


if __name__ == "__main__":
    sys.exit(main())
