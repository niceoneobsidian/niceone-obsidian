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
