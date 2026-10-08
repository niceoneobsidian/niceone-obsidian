"""Load and validate the canonical secret registry."""

from __future__ import annotations

import tomllib
from pathlib import Path

from .manager import SecretMetadata, SecretManager, SecretProvider

DEFAULT_REGISTRY = Path(__file__).resolve().parents[3] / "config" / "secrets" / "registry.toml"


def load_registry(path: Path = DEFAULT_REGISTRY) -> dict[str, SecretMetadata]:
    with path.open("rb") as handle:
        payload = tomllib.load(handle)
    if payload.get("version") != 1:
        raise ValueError("unsupported secret registry version")
    entries = payload.get("secrets")
    if not isinstance(entries, dict):
        raise ValueError("secret registry must contain a [secrets] table")
    result: dict[str, SecretMetadata] = {}
    for name, raw in entries.items():
        if not isinstance(raw, dict):
            raise ValueError(f"invalid secret metadata: {name}")
        environments = raw.get("environment", [])
        if not isinstance(environments, list) or not all(isinstance(x, str) for x in environments):
            raise ValueError(f"invalid environments for secret: {name}")
        scopes = raw.get("scopes", [])
        if not isinstance(scopes, list) or not all(isinstance(x, str) for x in scopes):
            raise ValueError(f"invalid scopes for secret: {name}")
        result[name] = SecretMetadata(
            name=name,
            provider=str(raw["provider"]),
            environment=",".join(environments),
            required=bool(raw.get("required", False)),
            scopes=tuple(scopes),
            rotation_days=int(raw["rotation_days"]) if raw.get("rotation_days") is not None else None,
        )
    return result


def manager_from_registry(
    provider: SecretProvider,
    path: Path = DEFAULT_REGISTRY,
) -> SecretManager:
    return SecretManager(provider, load_registry(path))
