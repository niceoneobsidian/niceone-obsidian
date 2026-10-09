"""CI gate for the OIS environment contract and secret hygiene."""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from ois.config.settings import validate_startup  # noqa: E402

SECRET_NAME = re.compile(
    r"(^|_)(SECRET|TOKEN|PASSWORD|API_KEY|PRIVATE_KEY)(_|$)",
    re.I,
)
NON_SECRET_CONFIG = re.compile(
    r"(^|_)(PROVIDER|REGISTRY|MANAGER|FAIL_CLOSED|SCAN|ENABLED|DISABLED|TTL|TIMEOUT|ROTATION|REDACTION|REDACT)(_|$)",
    re.I,
)


def check_example() -> list[str]:
    errors = []
    path = Path(".env.example")
    for line_no, line in enumerate(path.read_text().splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if SECRET_NAME.search(key) and not NON_SECRET_CONFIG.search(key) and value.strip():
            errors.append(f".env.example:{line_no}: secret-like variable must be empty")
    return errors


def main() -> int:
    errors = check_example()
    try:
        validate_startup(os.environ)
    except Exception as exc:
        errors.append(f"configuration: {exc}")
    if errors:
        for error in errors:
            print(f"FAIL {error}")
        return 1
    print("PASS OIS environment contract")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
