from __future__ import annotations

import subprocess
import sys


def test_strict_integration_certificate_passes() -> None:
    result = subprocess.run(
        [sys.executable, "scripts/verify_integration_certificate.py", "--strict"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
