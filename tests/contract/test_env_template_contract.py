"""Fail-closed contract for the OIS social runtime environment template.

The template is the documented default configuration. These tests prove that
copying it unchanged yields a deployment where nothing external can write or
publish, dry-run is on, kill switches are set, and no credential is present.
"""

from __future__ import annotations

import re
from pathlib import Path

TEMPLATE_PATH = Path(__file__).resolve().parents[2] / "config" / "ois-social.env.template"

PROVIDERS = (
    "EULERSTREAM",
    "EXOLYT",
    "PENTOS",
    "SOCIAVAULT",
    "BUNDLE_SOCIAL",
    "RAPIDAPI",
    "TIKTOK",
)

SECRET_KEY = re.compile(
    r"(_API_KEY|_SECRET|_ACCESS_TOKEN|_REFRESH_TOKEN|_CLIENT_KEY)$|^RAPIDAPI_KEY$"
)
BOOLEAN_KEY = re.compile(
    r"(_ENABLED|_DRY_RUN|_KILL_SWITCH|_REQUIRE_[A-Z_]+|_REDACT_[A-Z_]+|_REDACT)$"
)


def parse_env(text: str) -> tuple[dict[str, str], list[str]]:
    """Return (values, duplicate_keys); comments and blank lines are ignored."""
    values: dict[str, str] = {}
    duplicates: list[str] = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        key, sep, value = line.partition("=")
        if not sep:
            continue
        key = key.strip()
        if key in values:
            duplicates.append(key)
        values[key] = value.strip()
    return values, duplicates


def load() -> dict[str, str]:
    assert TEMPLATE_PATH.is_file(), f"missing environment template: {TEMPLATE_PATH}"
    values, _ = parse_env(TEMPLATE_PATH.read_text(encoding="utf-8"))
    return values


def mutating(key: str) -> bool:
    if "IDEMPOTENCY" in key:
        return False
    return "WRITE" in key or "PUBLISH" in key


def test_template_has_no_duplicate_keys() -> None:
    _, duplicates = parse_env(TEMPLATE_PATH.read_text(encoding="utf-8"))
    assert duplicates == []


def test_runtime_identity_defaults_are_non_production() -> None:
    env = load()
    assert env["OIS_ENVIRONMENT"] == "development"
    assert env["OIS_RUNTIME_MODE"] == "local"
    assert env["OIS_STARTUP_VALIDATION"] == "true"
    assert env["CONFIG_FAIL_ON_UNSAFE_PRODUCTION_SETTINGS"] == "true"


def test_master_external_gates_are_closed() -> None:
    env = load()
    closed = (
        "EXTERNAL_APIS_ENABLED",
        "EXTERNAL_API_READS_ENABLED",
        "EXTERNAL_API_WRITES_ENABLED",
        "EXTERNAL_DESTRUCTIVE_OPERATIONS_ENABLED",
        "SOCIAL_PUBLISHING_ENABLED",
        "PUBLISHING_ENABLED",
        "SOCIAL_INGESTION_ENABLED",
        "TIKTOK_OAUTH_ENABLED",
    )
    open_gates = [key for key in closed if env.get(key) != "false"]
    assert open_gates == []


def test_every_write_or_publish_enable_flag_is_false() -> None:
    env = load()
    offenders = {
        key: value
        for key, value in env.items()
        if key.endswith("_ENABLED") and mutating(key) and value != "false"
    }
    assert offenders == {}


def test_every_provider_is_disabled_by_default() -> None:
    env = load()
    offenders = [
        key
        for provider in PROVIDERS
        for key in (
            f"{provider}_ENABLED",
            f"{provider}_READ_ENABLED",
            f"{provider}_WRITE_ENABLED",
        )
        if env.get(key) != "false"
    ]
    assert offenders == []


def test_dry_run_is_on_everywhere() -> None:
    env = load()
    dry_run_keys = [key for key in env if key.endswith("_DRY_RUN")]
    assert {"EXTERNAL_API_DRY_RUN", "SOCIAL_PUBLISHING_DRY_RUN"} <= set(dry_run_keys)
    assert [key for key in dry_run_keys if env[key] != "true"] == []


def test_write_and_publish_kill_switches_are_set() -> None:
    env = load()
    required = (
        "EXTERNAL_WRITE_KILL_SWITCH",
        "PUBLISHING_KILL_SWITCH",
        "OIS_EXTERNAL_WRITE_KILL_SWITCH",
        "OIS_PUBLISHING_KILL_SWITCH",
    )
    assert [key for key in required if env.get(key) != "true"] == []
    unset = [
        key
        for key, value in env.items()
        if key.endswith("KILL_SWITCH") and mutating(key) and value != "true"
    ]
    assert unset == []


def test_policy_evidence_and_approval_gates_are_required() -> None:
    env = load()
    required = (
        "EXTERNAL_WRITES_REQUIRE_POLICY",
        "EXTERNAL_WRITES_REQUIRE_EVIDENCE",
        "EXTERNAL_WRITES_REQUIRE_APPROVAL",
        "PUBLISHING_REQUIRE_CAPABILITY",
        "PUBLISHING_REQUIRE_POLICY",
        "PUBLISHING_REQUIRE_APPROVAL",
        "PUBLISHING_REQUIRE_EVIDENCE",
        "PUBLISHING_IDEMPOTENCY_ENABLED",
        "CAPABILITY_REQUIRE_IMPLEMENTATION",
        "CAPABILITY_REQUIRE_TESTS",
        "CAPABILITY_REQUIRE_INTEGRATION",
        "CAPABILITY_REQUIRE_POLICY",
        "CAPABILITY_REQUIRE_ROLLBACK",
        "CAPABILITY_REQUIRE_PRODUCTION_VERIFICATION",
        "CAPABILITY_CONFIG_CANNOT_BYPASS_GATES",
        "SOCIAL_REQUIRE_REGISTERED_PROVIDER",
        "SOCIAL_REQUIRE_APPROVED_ENDPOINT",
    )
    assert [key for key in required if env.get(key) != "true"] == []


def test_secret_redaction_is_on_everywhere() -> None:
    env = load()
    redaction = [key for key in env if "REDACT" in key]
    assert len(redaction) >= 8
    assert [key for key in redaction if env[key] != "true"] == []


def test_transport_defaults_are_safe() -> None:
    env = load()
    assert env["HTTP_VERIFY_TLS"] == "true"
    assert env["HTTP_ALLOW_AUTH_REDIRECTS"] == "false"
    insecure = [
        key
        for key, value in env.items()
        if key.endswith("_BASE_URL") and value and not value.startswith("https://")
    ]
    assert insecure == []


def test_template_contains_no_credential_values() -> None:
    env = load()
    leaked = [key for key, value in env.items() if SECRET_KEY.search(key) and value]
    assert leaked == []


def test_boolean_flags_use_canonical_values() -> None:
    env = load()
    malformed = {
        key: value
        for key, value in env.items()
        if BOOLEAN_KEY.search(key) and value not in {"true", "false"}
    }
    assert malformed == {}
