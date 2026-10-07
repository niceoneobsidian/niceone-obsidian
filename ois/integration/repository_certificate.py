"""Repository-wide integration conformance certificate.

This layer binds the 23-column IntegrationConformance matrix to concrete
repository evidence: provider adapter source, registry/spec declarations,
tests, workflows, policy/configuration and production-verification artifacts.

It is deliberately fail-closed: repository presence alone never becomes live
or production verification.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from ois.infrastructure.source_adapters.base import SourceAdapterRegistry

from .conformance import (
    ConformanceReport,
    ConformanceStatus,
    IntegrationConformance,
)

DEFAULT_REGISTRY_FACTORY = (
    "ois.infrastructure.source_adapters.bootstrap:build_application_source_adapter_registry"
)


@dataclass(frozen=True)
class RepositoryEvidence:
    path: str
    kind: str
    detail: str


@dataclass(frozen=True)
class CertificatePolicy:
    """Mandatory dimensions for every registered/provider-discovered source."""

    required: tuple[str, ...] = (
        "ADAPTER",
        "REGISTRATION",
        "CAPABILITY",
        "PROVENANCE",
        "EVIDENCE",
        "STRUCTURAL TEST",
        "CONTRACT TEST",
        "CI GATE",
    )


@dataclass(frozen=True)
class IntegrationConformanceCertificate:
    schema_version: str
    commit: str | None
    report: ConformanceReport
    mandatory_columns: tuple[str, ...]
    certificate_hash: str
    valid: bool
    failures: tuple[str, ...]
    evidence: dict[str, tuple[RepositoryEvidence, ...]]

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "commit": self.commit,
            "mandatory_columns": list(self.mandatory_columns),
            "valid": self.valid,
            "failures": list(self.failures),
            "certificate_hash": self.certificate_hash,
            "report": self.report.to_dict(),
            "evidence": {
                source: [
                    {"path": item.path, "kind": item.kind, "detail": item.detail} for item in items
                ]
                for source, items in self.evidence.items()
            },
        }

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)


class RepositoryConformanceScanner:
    """Build evidence from the repository itself, without inventing runtime proof."""

    TEXT_SUFFIXES = {".py", ".md", ".yml", ".yaml", ".json", ".toml", ".txt"}

    def __init__(self, root: Path) -> None:
        self.root = root.resolve()

    def evidence_for(self, source_id: str) -> tuple[RepositoryEvidence, ...]:
        evidence: list[RepositoryEvidence] = []

        for path in self._files("ois", "tests", "docs", ".github", "manifests", "config"):
            if path.suffix not in self.TEXT_SUFFIXES:
                continue
            text = self._read(path)
            is_conformance_workflow = (
                ".github/workflows/" in str(path.relative_to(self.root)).lower()
                and "conformance" in str(path).lower()
            )
            if source_id not in text and not is_conformance_workflow:
                continue
            rel = str(path.relative_to(self.root))
            kind = self._kind(rel, text, source_id)
            if kind:
                evidence.append(RepositoryEvidence(rel, kind, source_id))

        return tuple(sorted(set(evidence), key=lambda item: (item.kind, item.path)))

    @staticmethod
    def _kind(path: str, text: str, source_id: str) -> str | None:
        lower = path.lower()
        content = text.lower()
        if "/tests/" in lower or lower.startswith("tests/"):
            if "structure" in lower or "structural" in lower:
                return "STRUCTURAL_TEST"
            if "live" in lower or "live_" in content or "phase_a" in lower:
                return "LIVE_TEST"
            if "contract" in lower or "contract" in content:
                return "CONTRACT_TEST"
            if "negative" in lower or "security" in lower or "permission" in content:
                return "NEGATIVE_TEST"
            return "STRUCTURAL_TEST"
        if ".github/workflows/" in lower:
            return "CI"
        if lower.startswith("docs/"):
            if "production" in lower or "verification" in lower:
                return "PRODUCTION_DOCUMENTATION"
            return "DOCUMENTATION"
        if lower.startswith("manifests/"):
            if "production" in lower or "readiness" in lower:
                return "PRODUCTION_MANIFEST"
            return "MANIFEST"
        if lower.startswith("ois/"):
            if "source_gateway" in lower:
                return "GATEWAY"
            if "registry" in lower:
                return "REGISTRY"
            return "IMPLEMENTATION"
        if lower.startswith("config/"):
            return "POLICY_CONFIG"
        return None

    def _files(self, *roots: str) -> Iterable[Path]:
        for root in roots:
            base = self.root / root
            if not base.exists():
                continue
            for path in base.rglob("*"):
                if path.is_file() and ".git" not in path.parts:
                    yield path

    @staticmethod
    def _read(path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            return ""


class RepositoryConformanceCertificateBuilder:
    """Build a certificate from canonical registry conformance plus evidence."""

    def __init__(
        self,
        root: Path,
        *,
        registry: SourceAdapterRegistry,
        policy: CertificatePolicy | None = None,
        commit: str | None = None,
    ) -> None:
        self.scanner = RepositoryConformanceScanner(root)
        self.registry = registry
        self.policy = policy or CertificatePolicy()
        self.commit = commit

    def build(self) -> IntegrationConformanceCertificate:
        base_report = IntegrationConformance(self.registry).audit()
        evidence_map = {
            record.source_id: self.scanner.evidence_for(record.source_id)
            for record in base_report.records
        }

        evidence_to_column = {
            "STRUCTURAL_TEST": "STRUCTURAL TEST",
            "CONTRACT_TEST": "CONTRACT TEST",
            "CI": "CI GATE",
        }

        enriched_records = []
        for record in base_report.records:
            cells = dict(record.cells)

            for item in evidence_map[record.source_id]:
                column = evidence_to_column.get(item.kind)
                if column is None:
                    continue

                existing = cells[column]
                cells[column] = existing.__class__(
                    status=ConformanceStatus.TESTED,
                    evidence=existing.evidence + (f"{item.kind}:{item.path}",),
                    note=existing.note,
                )

            enriched_records.append(
                record.__class__(
                    provider_id=record.provider_id,
                    source_id=record.source_id,
                    cells=cells,
                )
            )

        report = ConformanceReport(tuple(enriched_records))
        failures: list[str] = []

        if not report.records:
            failures.append("REGISTRY_EMPTY")

        for record in report.records:
            for column in self.policy.required:
                status = record.cells[column].status
                if status in {
                    ConformanceStatus.UNKNOWN,
                    ConformanceStatus.MISSING,
                }:
                    failures.append(f"{record.source_id}:{column}={status.value}")

        payload = {
            "schema_version": "ois.integration.conformance.certificate.v2",
            "commit": self.commit,
            "mandatory_columns": list(self.policy.required),
            "report": report.to_dict(),
            "evidence": {
                key: [item.__dict__ for item in value]
                for key, value in sorted(evidence_map.items())
            },
        }

        digest = hashlib.sha256(
            json.dumps(
                payload,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()

        return IntegrationConformanceCertificate(
            schema_version="ois.integration.conformance.certificate.v2",
            commit=self.commit,
            report=report,
            mandatory_columns=self.policy.required,
            certificate_hash=digest,
            valid=bool(report.records) and not failures,
            failures=tuple(sorted(set(failures))),
            evidence=evidence_map,
        )


def build_repository_certificate(
    root: Path,
    *,
    registry: SourceAdapterRegistry,
    policy: CertificatePolicy | None = None,
    commit: str | None = None,
) -> IntegrationConformanceCertificate:
    return RepositoryConformanceCertificateBuilder(
        root,
        registry=registry,
        policy=policy,
        commit=commit,
    ).build()


def _load_registry(factory_path: str) -> SourceAdapterRegistry:
    """Load the canonical application registry factory by module path."""
    if ":" not in factory_path:
        raise ValueError("registry factory must use module:function syntax")

    module_name, function_name = factory_path.split(":", 1)
    factory = getattr(importlib.import_module(module_name), function_name, None)
    if not callable(factory):
        raise TypeError(f"registry factory is not callable: {factory_path}")

    registry = factory()
    if not isinstance(registry, SourceAdapterRegistry):
        raise TypeError(f"registry factory must return SourceAdapterRegistry: {factory_path}")
    return registry


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".")
    parser.add_argument("--output", default="integration-conformance-certificate.json")
    parser.add_argument("--commit", default=None)
    parser.add_argument("--strict", action="store_true")
    parser.add_argument("--registry-factory", default=DEFAULT_REGISTRY_FACTORY)
    args = parser.parse_args(argv)

    certificate = build_repository_certificate(
        Path(args.root),
        registry=_load_registry(args.registry_factory),
        commit=args.commit,
    )
    Path(args.output).write_text(certificate.to_json() + "\n", encoding="utf-8")
    print(certificate.to_json())
    return 1 if args.strict and not certificate.valid else 0


if __name__ == "__main__":
    raise SystemExit(main())
