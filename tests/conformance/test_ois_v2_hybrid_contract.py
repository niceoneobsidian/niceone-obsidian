from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_ois_v2_hybrid_contract_is_safe_and_repository_anchored() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/validate_ois_v2_hybrid.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
