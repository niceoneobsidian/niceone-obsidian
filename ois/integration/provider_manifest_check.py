"""Strict, fail-closed validation of provider conformance manifests.

A manifest is a *declaration*. This module only accepts a declaration when it
agrees with what the canonical ``SourceAdapterRegistry`` actually contains
(SourceSpec, registered conformance metadata, adapter timeout) and when every
referenced evidence path exists inside the repository. Fields that nothing in
the code proves must be listed in ``unknown`` and must be empty; verification
states beyond ``UNKNOWN`` are rejected until a later stage supplies real proof.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ois.infrastructure.source_adapters.base import SourceAdapterRegistry

from .provider_manifest import load_manifest

DEFAULT_MANIFEST_DIR = "manifests/providers"
REGISTRATION_FACTORY = (
    "ois.infrastructure.source_adapters.bootstrap:build_application_source_adapter_registry"
)
# Behaviour that no registry metadata proves today. Must be declared unknown
# (and empty) unless a claim carries existing evidence paths.
UNVERIFIED_FIELDS = (
    "tools",
    "auth_schemes",
    "credential_types",
    "scopes",
    "policy_actions",
    "rate_limit",
    "retry",
    "idempotency",
    "events",
)
VERIFICATION_KEYS = ("live", "e2e", "negative", "production")
CLAIM_COLUMNS = ("ADAPTER", "REGISTRATION", "CAPABILITY", "TIMEOUT")


def _fail(source_id: str, reason: str) -> str:
    return f"{source_id}:MANIFEST:{reason}"


def _empty(value: Any) -> bool:
    return value in (None, "", [], (), {})


def _adapter_timeout(adapter: Any) -> float | None:
    for holder in (adapter, getattr(adapter, "_http", None)):
        value = getattr(holder, "_timeout", None)
        if isinstance(value, (int, float)):
            return float(value)
    return None


def _check_path(root: Path, rel: str) -> str | None:
    candidate = (root / rel).resolve()
    try:
        candidate.relative_to(root.resolve())
    except ValueError:
        return f"evidence-outside-root={rel}"
    if not candidate.is_file():
        return f"evidence-missing={rel}"
    return None


def load_manifest_documents(manifest_dir: Path) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Index manifest JSON documents by provider id; report unreadable files."""
    docs: dict[str, dict[str, Any]] = {}
    problems: list[str] = []
    if not manifest_dir.is_dir():
        return docs, problems
    for path in sorted(manifest_dir.glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            problems.append(f"{path.name}:MANIFEST:unreadable-json")
            continue
        provider = data.get("provider") if isinstance(data, dict) else None
        if not isinstance(provider, str) or not provider:
            problems.append(f"{path.name}:MANIFEST:missing-provider-id")
        elif provider in docs:
            problems.append(f"{provider}:MANIFEST:duplicate")
        else:
            docs[provider] = data
    return docs, problems


def validate_provider_manifests(
    root: Path,
    registry: SourceAdapterRegistry,
    manifest_dir: Path | None = None,
) -> tuple[str, ...]:
    """Return sorted failure strings; an empty tuple means consistent."""
    root = root.resolve()
    directory = manifest_dir or (root / DEFAULT_MANIFEST_DIR)
    docs, failures = load_manifest_documents(directory)
    registered = list(registry.list())

    for source_id in sorted(set(docs) - set(registered)):
        failures.append(_fail(source_id, "orphan-manifest-not-in-registry"))

    for source_id in registered:
        doc = docs.get(source_id)
        if doc is None:
            failures.append(_fail(source_id, "missing"))
            continue
        failures.extend(_validate_one(root, registry, source_id, doc))
    return tuple(sorted(set(failures)))


def _validate_one(
    root: Path,
    registry: SourceAdapterRegistry,
    source_id: str,
    doc: Mapping[str, Any],
) -> list[str]:
    out: list[str] = []
    try:
        manifest = load_manifest(doc)
    except (ValueError, TypeError, AttributeError) as exc:
        return [_fail(source_id, f"invalid:{exc}")]

    spec = registry.spec(source_id)
    metadata = registry.conformance(source_id)

    if manifest.registration != REGISTRATION_FACTORY:
        out.append(_fail(source_id, "registration-not-canonical-factory"))
    if sorted(manifest.capabilities) != sorted(spec.capabilities):
        out.append(_fail(source_id, "capabilities-differ-from-SourceSpec"))
    meta = manifest.metadata
    for key, actual in (("protocol", spec.protocol), ("version", spec.version)):
        if meta.get(key) != actual:
            out.append(_fail(source_id, f"{key}-differs-from-SourceSpec"))

    if manifest.timeout_seconds is not None:
        actual_timeout = _adapter_timeout(registry.get(source_id))
        if actual_timeout is None or float(manifest.timeout_seconds) != actual_timeout:
            out.append(_fail(source_id, "timeout-differs-from-adapter"))

    out.extend(_validate_evidence(root, source_id, doc, metadata, manifest.adapter))
    out.extend(_validate_unknowns(root, source_id, doc, manifest))
    out.extend(_validate_verification(source_id, doc))
    return out


def _validate_evidence(
    root: Path,
    source_id: str,
    doc: Mapping[str, Any],
    metadata: Any,
    adapter_path: str,
) -> list[str]:
    out: list[str] = []
    problem = _check_path(root, adapter_path)
    if problem:
        out.append(_fail(source_id, f"adapter-{problem}"))
    claims = (doc.get("evidence") or {}).get("claims")
    if not isinstance(claims, Mapping):
        return [*out, _fail(source_id, "evidence-claims-missing")]
    for column in CLAIM_COLUMNS:
        paths = claims.get(column)
        if not paths or not isinstance(paths, list):
            out.append(_fail(source_id, f"{column}-evidence-missing"))
            continue
        registered = (
            set(metadata.claims[column].evidence)
            if metadata and column in metadata.claims
            else set()
        )
        for rel in paths:
            problem = _check_path(root, str(rel))
            if problem:
                out.append(_fail(source_id, f"{column}-{problem}"))
            elif str(rel) not in registered:
                out.append(_fail(source_id, f"{column}-evidence-not-in-registry-metadata={rel}"))
    if metadata and adapter_path not in metadata.claims["ADAPTER"].evidence:
        out.append(_fail(source_id, "adapter-path-differs-from-registry-metadata"))
    return out


def _validate_unknowns(
    root: Path, source_id: str, doc: Mapping[str, Any], manifest: Any
) -> list[str]:
    out: list[str] = []
    unknown = doc.get("unknown")
    if not isinstance(unknown, list):
        return [_fail(source_id, "unknown-list-missing")]
    values = {
        "tools": manifest.tools,
        "auth_schemes": manifest.auth_schemes,
        "credential_types": manifest.credential_types,
        "scopes": manifest.scopes,
        "policy_actions": manifest.policy_actions,
        "rate_limit": manifest.rate_limit,
        "retry": manifest.retry,
        "idempotency": manifest.idempotency,
        "events": manifest.events,
    }
    claims = (doc.get("evidence") or {}).get("claims") or {}
    for name in UNVERIFIED_FIELDS:
        value = values[name]
        if name in unknown:
            if not _empty(value):
                out.append(_fail(source_id, f"{name}-declared-unknown-but-populated"))
        elif _empty(value) or not claims.get(name.upper()):
            out.append(_fail(source_id, f"{name}-neither-unknown-nor-evidenced"))
        else:
            for rel in claims[name.upper()]:
                problem = _check_path(root, str(rel))
                if problem:
                    out.append(_fail(source_id, f"{name}-{problem}"))
    for name in unknown:
        if name not in UNVERIFIED_FIELDS:
            out.append(_fail(source_id, f"unknown-field-not-recognised={name}"))
    return out


def _validate_verification(source_id: str, doc: Mapping[str, Any]) -> list[str]:
    out: list[str] = []
    verification = doc.get("verification")
    if not isinstance(verification, Mapping):
        return [_fail(source_id, "verification-block-missing")]
    for key in VERIFICATION_KEYS:
        if verification.get(key) != "UNKNOWN":
            out.append(_fail(source_id, f"unsupported-verification-claim:{key}"))
    live = doc.get("live") or {}
    if live.get("verified") not in (None, False):
        out.append(_fail(source_id, "unsupported-verification-claim:live.verified"))
    return out
