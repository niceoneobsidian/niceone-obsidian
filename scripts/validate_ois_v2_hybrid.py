"""Validate the canonical OIS v2 Hybrid environment contract against repository reality.

This validator intentionally distinguishes:
- configuration safety (must be true now),
- repository anchors (must exist now), and
- declarations that remain architectural/future-facing.

It does not promote a declaration to production readiness.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = ROOT / ".env.example"

REQUIRED_FILES = {
    "source gateway credentials": "ois/infrastructure/source_gateway/credentials.py",
    "source adapter registry": "ois/infrastructure/source_adapters/base.py",
    "github source": "ois/integrations/github/source.py",
    "kernel policy": "ois/kernel/policy.py",
    "kernel contracts": "ois/kernel/contracts.py",
    "tool registry": "ois/registries/core.py",
    "tenant RLS conformance": "tests/integration/test_p0_4_4_rls_adversarial.py",
    "live integration tests": "tests/integrations/test_phase_a_live.py",
    "phase gates": "config/phase-gates.json",
    "P0 CI": ".github/workflows/p0-conformance.yml",
}

REQUIRED_SYMBOLS = {
    "credential resolver": (
        "ois/infrastructure/source_gateway/credentials.py",
        "class CredentialResolver",
    ),
    "tenant scope": (
        "ois/infrastructure/source_gateway/credentials.py",
        "class TenantScope",
    ),
    "adapter registry": (
        "ois/infrastructure/source_adapters/base.py",
        "class SourceAdapterRegistry",
    ),
    "github source id": (
        "ois/integrations/github/source.py",
        'source_id = "github.rest.user"',
    ),
    "policy engine": ("ois/kernel/contracts.py", "class PolicyEngine"),
    "tool registry": ("ois/registries/core.py", "class ToolRegistry"),
}

REQUIRED_ENV = (
    "OIS_ALLOW_EXTERNAL_CALLS",
    "OIS_EXTERNAL_WRITE_ENABLED",
    "OIS_EXTERNAL_DELETE_ENABLED",
    "OIS_EXTERNAL_PUBLISH_ENABLED",
    "OIS_FAIL_CLOSED",
    "INTEGRATIONS_REQUIRE_REGISTRATION",
    "INTEGRATIONS_REQUIRE_CAPABILITY",
    "INTEGRATIONS_REQUIRE_POLICY",
    "INTEGRATIONS_REQUIRE_TOOL_REGISTRY",
    "INTEGRATIONS_REQUIRE_CREDENTIAL_RESOLUTION",
    "OIS_CREDENTIAL_RESOLVER_ENABLED",
    "OIS_CREDENTIAL_RESOLUTION_FAIL_CLOSED",
    "OIS_POLICY_ENGINE_ENABLED",
    "OIS_POLICY_FAIL_CLOSED",
    "OIS_TENANT_ISOLATION_ENABLED",
    "OIS_CONFORMANCE_ENABLED",
    "OIS_CONFORMANCE_SECURITY_TESTS_ENABLED",
    "OIS_CONFORMANCE_NEGATIVE_TESTS_ENABLED",
    "OIS_CONFORMANCE_LIVE_TESTS_ENABLED",
    "OIS_INTEGRATION_TEST_MODE",
    "OIS_LIVE_PHASE_A",
    "OIS_LIVE_TEST_READ_ONLY",
    "OIS_FIRST_LIVE_PROVIDER",
    "OIS_FIRST_LIVE_CAPABILITY",
    "GITHUB_ENABLED",
    "GITHUB_LIVE_TEST_ENABLED",
    "OIS_ASSERT_SAFE_DEFAULTS",
)

SAFE_EXPECTATIONS = {
    "OIS_ALLOW_EXTERNAL_CALLS": "false",
    "OIS_EXTERNAL_WRITE_ENABLED": "false",
    "OIS_EXTERNAL_DELETE_ENABLED": "false",
    "OIS_EXTERNAL_PUBLISH_ENABLED": "false",
    "OIS_FAIL_CLOSED": "true",
    "INTEGRATIONS_REQUIRE_REGISTRATION": "true",
    "INTEGRATIONS_REQUIRE_CAPABILITY": "true",
    "INTEGRATIONS_REQUIRE_POLICY": "true",
    "INTEGRATIONS_REQUIRE_TOOL_REGISTRY": "true",
    "INTEGRATIONS_REQUIRE_CREDENTIAL_RESOLUTION": "true",
    "OIS_CREDENTIAL_RESOLVER_ENABLED": "true",
    "OIS_CREDENTIAL_RESOLUTION_FAIL_CLOSED": "true",
    "OIS_POLICY_ENGINE_ENABLED": "true",
    "OIS_POLICY_FAIL_CLOSED": "true",
    "OIS_TENANT_ISOLATION_ENABLED": "true",
    "OIS_CONFORMANCE_ENABLED": "true",
    "OIS_CONFORMANCE_SECURITY_TESTS_ENABLED": "true",
    "OIS_CONFORMANCE_NEGATIVE_TESTS_ENABLED": "true",
    "OIS_CONFORMANCE_LIVE_TESTS_ENABLED": "false",
    "OIS_INTEGRATION_TEST_MODE": "offline",
    "OIS_LIVE_PHASE_A": "false",
    "OIS_LIVE_TEST_READ_ONLY": "true",
    "OIS_FIRST_LIVE_PROVIDER": "github",
    "OIS_FIRST_LIVE_CAPABILITY": "github.rest.user",
    "GITHUB_ENABLED": "false",
    "GITHUB_LIVE_TEST_ENABLED": "false",
    "OIS_ASSERT_SAFE_DEFAULTS": "true",
}

FORBIDDEN_SECRET_ASSIGNMENTS = re.compile(
    r"^(?:[A-Z0-9_]+_(?:SECRET|PASSWORD|TOKEN|PRIVATE_KEY|API_KEY|PAT))="
)


def parse_env(text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def main() -> int:
    errors: list[str] = []
    warnings: list[str] = []

    if not ENV_FILE.is_file():
        errors.append(f"missing canonical contract: {ENV_FILE}")
        print("\n".join(f"ERROR: {item}" for item in errors))
        return 1

    env_text = ENV_FILE.read_text(encoding="utf-8")
    values = parse_env(env_text)

    for key in REQUIRED_ENV:
        if key not in values:
            errors.append(f"missing required hybrid contract variable: {key}")

    for key, expected in SAFE_EXPECTATIONS.items():
        actual = values.get(key)
        if actual != expected:
            errors.append(
                f"unsafe/non-canonical default: {key}={actual!r}; expected {expected!r}"
            )

    for line in env_text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if FORBIDDEN_SECRET_ASSIGNMENTS.match(line):
            key, value = line.split("=", 1)
            if value.strip():
                errors.append(f"populated secret in canonical example: {key}")

    for label, relative in REQUIRED_FILES.items():
        path = ROOT / relative
        if not path.is_file():
            errors.append(f"missing repository anchor [{label}]: {relative}")

    for label, (relative, needle) in REQUIRED_SYMBOLS.items():
        path = ROOT / relative
        if not path.is_file():
            continue
        content = path.read_text(encoding="utf-8")
        if needle not in content:
            errors.append(f"missing implementation anchor [{label}]: {needle}")

    live_test = ROOT / "tests/integrations/test_phase_a_live.py"
    if live_test.is_file():
        content = live_test.read_text(encoding="utf-8")
        if "OIS_LIVE_PHASE_A" not in content:
            errors.append("live integration gate is not tied to OIS_LIVE_PHASE_A")
        if "OIS_LIVE_GITHUB_ACCESS_TOKEN" not in content:
            warnings.append(
                "GitHub live test still uses its legacy protected token variable; "
                "credential-ref wiring should replace it before production live testing."
            )

    phase_gates = ROOT / "config/phase-gates.json"
    if phase_gates.is_file():
        content = phase_gates.read_text(encoding="utf-8")
        for gate in (
            "Security / Tenant Isolation",
            "Observability",
            "Real External APIs",
            "Production Canary",
        ):
            if gate not in content:
                errors.append(f"phase-gate evidence missing: {gate}")

    if errors:
        for item in errors:
            print(f"ERROR: {item}")
        for item in warnings:
            print(f"WARNING: {item}")
        return 1

    print("OIS v2 Hybrid contract validation: PASS")
    print(f"Canonical variables: {len(values)}")
    print("Safety defaults: PASS")
    print("Repository architecture anchors: PASS")
    print("Phase/conformance anchors: PASS")
    for item in warnings:
        print(f"WARNING: {item}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
