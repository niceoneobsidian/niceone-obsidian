"""Startup configuration verification entry point."""

from __future__ import annotations

import json
from collections.abc import Mapping

from .settings import validate_startup


def startup_report(env: Mapping[str, str] | None = None) -> dict[str, object]:
    s = validate_startup(env)
    return {
        "status": "PASS",
        "environment": s.environment,
        "config_profile": s.config_profile,
        "external_apis_enabled": s.external_apis_enabled,
        "external_reads_enabled": s.external_reads_enabled,
        "external_writes_enabled": s.external_writes_enabled,
        "secret_provider": s.secret_provider,
        "validation_required": s.require_validation,
        "capability_evidence_required": s.require_capability_evidence,
    }


def main() -> int:
    try:
        print(json.dumps(startup_report(), indent=2, sort_keys=True))
    except Exception as exc:
        print(json.dumps({"status": "FAIL", "error": str(exc)}, indent=2))
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
