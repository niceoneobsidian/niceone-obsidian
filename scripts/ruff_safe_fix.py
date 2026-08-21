"""Apply Ruff's safe autofixes to the OIS source tree.

This helper is intentionally separate from CI so automated remediation is
explicit and reviewable rather than mutating files during a workflow run.
"""
from __future__ import annotations

import subprocess
import sys


def main() -> int:
    command = [sys.executable, "-m", "ruff", "check", ".", "--fix"]
    return subprocess.call(command)


if __name__ == "__main__":
    raise SystemExit(main())
