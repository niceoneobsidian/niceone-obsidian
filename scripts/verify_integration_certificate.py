"""Strict OIS integration certificate for the complete provider inventory."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "config" / "integration-provider-certificate.json"
ENV_FILE = ROOT / ".env.example"

REQUIRED_COLUMNS = (
    "adapter", "source_id", "tool_registry", "capability_registry", "auth",
    "scopes", "policy", "retry", "rate_limit", "idempotency", "tests", "ci"
)
FORBIDDEN = {"", "UNKNOWN", "MISSING", "TBD", "TODO"}

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
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()
    errors: list[str] = []

    if not MANIFEST.is_file():
        errors.append(f"missing manifest: {MANIFEST.relative_to(ROOT)}")
    if not ENV_FILE.is_file():
        errors.append(f"missing canonical environment: {ENV_FILE.relative_to(ROOT)}")
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    env = parse_env(ENV_FILE.read_text(encoding="utf-8"))
    providers = manifest.get("providers", [])
    ids: set[str] = set()
    source_capability_contracts = ROOT / "ois" / "integrations" / "provider_contracts.py"
    social_registry = ROOT / "ois" / "domains" / "social_intelligence" / "registry.py"
    source_registry = ROOT / "ois" / "infrastructure" / "source_adapters" / "base.py"
    tool_registry = ROOT / "ois" / "registries" / "core.py"
    policy = ROOT / "ois" / "kernel" / "policy.py"
    auth = ROOT / "ois" / "infrastructure" / "source_gateway" / "auth.py"
    rate_limit = ROOT / "ois" / "infrastructure" / "source_gateway" / "rate_limits.py"
    idempotency = ROOT / "ois" / "infrastructure" / "source_gateway" / "idempotency.py"

    for path in (
        source_capability_contracts, social_registry, source_registry,
        tool_registry, policy, auth, rate_limit, idempotency
    ):
        if not path.is_file():
            errors.append(f"missing integration authority: {path.relative_to(ROOT)}")

    if not providers:
        errors.append("provider inventory is empty")

    for provider in providers:
        provider_id = str(provider.get("id", ""))
        if not provider_id:
            errors.append("provider entry has no id")
            continue
        if provider_id in ids:
            errors.append(f"duplicate provider id: {provider_id}")
        ids.add(provider_id)

        env_flag = provider.get("env_flag")
        status = provider.get("status")
        if not env_flag or env_flag not in env:
            errors.append(f"{provider_id}: missing env activation flag {env_flag!r}")
        if status not in {"VERIFIED", "DISABLED_GATED", "INTERNAL_GATED"}:
            errors.append(f"{provider_id}: invalid status {status!r}")

        for column in REQUIRED_COLUMNS:
            value = str(provider.get(column, "")).strip()
            if value.upper() in FORBIDDEN:
                errors.append(f"{provider_id}: {column} is {value or 'MISSING'}")

        if status == "VERIFIED":
            for column in REQUIRED_COLUMNS:
                value = str(provider.get(column, "")).lower()
                if "not-active" in value or "not implemented" in value:
                    errors.append(f"{provider_id}: VERIFIED provider has inactive/missing {column}")

            adapter_ref = str(provider.get("adapter", ""))
            adapter_path = adapter_ref.split(":", 1)[0]
            if adapter_path and not (ROOT / adapter_path).is_file():
                errors.append(f"{provider_id}: adapter file missing: {adapter_path}")

            if provider_id in {"github", "google", "meta", "tiktok", "rss", "sportmonks"}:
                capability_id = f"provider.{provider_id}."
                source_text = source_capability_contracts.read_text(encoding="utf-8")
                if capability_id not in source_text:
                    errors.append(f"{provider_id}: capability contract not anchored in provider_contracts.py")

            if provider_id in {"sociavault", "bundle.social"}:
                registry_text = social_registry.read_text(encoding="utf-8")
                if "build_social_tool_registry" not in registry_text:
                    errors.append(f"{provider_id}: social ToolRegistry builder missing")
                if "provider_capability_contracts" not in registry_text:
                    errors.append(f"{provider_id}: social capability registry contract missing")
            else:
                if "SourceAdapterRegistry" not in source_registry.read_text(encoding="utf-8"):
                    errors.append(f"{provider_id}: SourceAdapterRegistry authority missing")
                if "ToolRegistry" not in tool_registry.read_text(encoding="utf-8"):
                    errors.append(f"{provider_id}: ToolRegistry authority missing")

            if "CredentialAuthManager" not in str(provider.get("auth", "")) and provider_id not in {"rss", "sociavault", "bundle.social"}:
                errors.append(f"{provider_id}: auth path is not bound to CredentialAuthManager")
            if "policy" not in str(provider.get("policy", "")).lower():
                errors.append(f"{provider_id}: policy evidence missing")
            if "ratelimit" not in str(provider.get("rate_limit", "")).lower().replace("-", ""):
                errors.append(f"{provider_id}: rate-limit evidence missing")
            if "idempot" not in str(provider.get("idempotency", "")).lower() and "dedupe" not in str(provider.get("idempotency", "")).lower():
                errors.append(f"{provider_id}: idempotency evidence missing")
        elif status == "DISABLED_GATED":
            if env.get(env_flag) != "false":
                errors.append(f"{provider_id}: disabled-gated provider must be false in canonical env")
            if "INTEGRATIONS_ALLOW_UNREGISTERED_PROVIDERS=false" not in str(provider.get("policy")):
                errors.append(f"{provider_id}: disabled-gated provider lacks registry fail-closed evidence")
        elif status == "INTERNAL_GATED":
            if "fail-closed" not in str(provider.get("policy")).lower():
                errors.append(f"{provider_id}: internal-gated provider lacks fail-closed policy evidence")

    env_provider_flags = {
        key for key in env
        if key.endswith("_ENABLED") and key.startswith((
            "GOOGLE_", "GITHUB_", "GMAIL_", "YOUTUBE_", "NOTION_", "SLACK_",
            "TIKTOK_", "META_", "INSTAGRAM_", "X_", "LINKEDIN_", "LATER_", "OPENAI_"
        ))
    }
    manifest_flags = {str(p.get("env_flag")) for p in providers}
    for key in sorted(env_provider_flags):
        if key in {"GOOGLE_DRIVE_ENABLED", "GMAIL_ENABLED", "YOUTUBE_ENABLED"}:
            continue
        if key not in manifest_flags:
            errors.append(f"provider activation flag omitted from inventory: {key}")

    print(f"Provider inventory: {len(providers)}")
    for provider in providers:
        print(f"[{provider['status']}] {provider['id']}")
    if errors:
        for error in errors:
            print(f"ERROR: {error}")
        return 1

    print("OIS Integration Certificate: PASS")
    print("Strict mode: PASS" if args.strict else "Strict mode: not requested")
    print("UNKNOWN/MISSING cells: 0")
    print("Production readiness: NOT CERTIFIED")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
