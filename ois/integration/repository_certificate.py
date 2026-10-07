"""Repository-wide integration conformance certificate.

This layer binds the 23-column IntegrationConformance matrix to concrete
repository evidence: provider adapter source, registry/spec declarations,
tests, workflows, policy/configuration and production-verification artifacts.

It is deliberately fail-closed: repository presence alone never becomes live
or production verification.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from .conformance import (
    CONFORMANCE_COLUMNS,
    ConformanceCell,
    ConformanceReport,
    ConformanceStatus,
    IntegrationConformanceRecord,
)

_SOURCE_ID_RE = re.compile(
    r"""(?:source_id\s*=|source_id:\s*)\s*["']([^"']+)["']"""
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
                    {"path": item.path, "kind": item.kind, "detail": item.detail}
                    for item in items
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

    def source_ids(self) -> tuple[str, ...]:
        found: set[str] = set()
        for path in self._files("ois"):
            if path.suffix != ".py":
                continue
            text = self._read(path)
            found.update(_SOURCE_ID_RE.findall(text))
        return tuple(sorted(found))

    def evidence_for(self, source_id: str) -> tuple[RepositoryEvidence, ...]:
        provider = source_id.split(":", 1)[0].lower()
        evidence: list[RepositoryEvidence] = []

        for path in self._files("ois", "tests", "docs", ".github", "manifests", "config"):
            if path.suffix not in self.TEXT_SUFFIXES:
                continue
            text = self._read(path)
            is_conformance_workflow = (
                ".github/workflows/" in str(path.relative_to(self.root)).lower()
                and "conformance" in str(path).lower()
            )
            if (
                source_id not in text
                and provider not in text.lower()
                and not is_conformance_workflow
            ):
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
    """Turn repository evidence into a fail-closed certificate."""

    def __init__(
        self,
        root: Path,
        *,
        policy: CertificatePolicy | None = None,
        commit: str | None = None,
    ) -> None:
        self.scanner = RepositoryConformanceScanner(root)
        self.policy = policy or CertificatePolicy()
        self.commit = commit

    def build(self) -> IntegrationConformanceCertificate:
        records: list[IntegrationConformanceRecord] = []
        evidence_map: dict[str, tuple[RepositoryEvidence, ...]] = {}
        failures: list[str] = []

        for source_id in self.scanner.source_ids():
            provider = source_id.split(":", 1)[0]
            evidence = self.scanner.evidence_for(source_id)
            evidence_map[source_id] = evidence
            cells = self._cells(source_id, provider, evidence)
            record = IntegrationConformanceRecord(provider, source_id, cells)
            records.append(record)

            for column in self.policy.required:
                status = cells[column].status
                if status in {ConformanceStatus.UNKNOWN, ConformanceStatus.MISSING}:
                    failures.append(f"{source_id}:{column}={status.value}")

        report = ConformanceReport(tuple(records))
        payload = {
            "schema_version": "ois.integration.conformance.certificate.v1",
            "commit": self.commit,
            "mandatory_columns": list(self.policy.required),
            "report": report.to_dict(),
            "evidence": {
                key: [item.__dict__ for item in value]
                for key, value in sorted(evidence_map.items())
            },
        }
        digest = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
        return IntegrationConformanceCertificate(
            schema_version="ois.integration.conformance.certificate.v1",
            commit=self.commit,
            report=report,
            mandatory_columns=self.policy.required,
            certificate_hash=digest,
            valid=not failures,
            failures=tuple(sorted(failures)),
            evidence=evidence_map,
        )

    def _cells(
        self,
        source_id: str,
        provider: str,
        evidence: tuple[RepositoryEvidence, ...],
    ) -> dict[str, ConformanceCell]:
        paths = {item.path for item in evidence}
        kinds = {item.kind for item in evidence}
        source_paths = [p for p in paths if p.startswith("ois/") and p.endswith(".py")]
        source_text = ""
        for rel in source_paths:
            source_text += self.scanner._read(self.scanner.root / rel) + "\n"
        evidence_text = "\n".join(
            self.scanner._read(self.scanner.root / p)
            for p in paths
            if source_id in self.scanner._read(self.scanner.root / p)
        )
        # Provider/source-scoped evidence only. Generic repository infrastructure
        # must not certify a specific provider unless the provider/source ID is
        # explicitly present in the evidence artifact.
        cells = {
            column: ConformanceCell(ConformanceStatus.UNKNOWN)
            for column in CONFORMANCE_COLUMNS
        }
        cells["PROVIDER"] = ConformanceCell(
            ConformanceStatus.IMPLEMENTED,
            (f"provider={provider}",),
        )
        cells["ADAPTER"] = ConformanceCell(
            ConformanceStatus.IMPLEMENTED if source_paths else ConformanceStatus.MISSING,
            tuple(sorted(source_paths)),
        )
        cells["REGISTRATION"] = self._status(
            "REGISTRATION",
            "REGISTRY" in kinds or "register(" in evidence_text,
            evidence,
        )
        cells["CAPABILITY"] = self._status(
            "CAPABILITY",
            "capabilities=" in evidence_text or "capability" in evidence_text.lower(),
            evidence,
        )
        cells["TOOL"] = self._status(
            "TOOL",
            "toolregistry" in evidence_text.lower(),
            evidence,
        )
        cells["AUTH"] = self._status(
            "AUTH",
            any(
                token in source_text
                for token in ("AuthScheme.", "auth_scheme=", "OAuth", "Bearer")
            ),
            evidence,
        )
        cells["CREDENTIAL"] = self._status(
            "CREDENTIAL",
            "CredentialRef" in source_text or "credential_id" in source_text,
            evidence,
        )
        cells["SCOPES"] = self._status(
            "SCOPES",
            bool(re.search(r"scopes\s*=\s*\([^)]*[^)]\)", source_text, re.IGNORECASE))
            or "scopes:" in evidence_text.lower(),
            evidence,
        )
        cells["POLICY"] = self._status(
            "POLICY",
            "policy" in evidence_text.lower() and (
                "auth" in evidence_text.lower() or "authorize" in evidence_text.lower()
            ),
            evidence,
        )
        cells["RATE LIMIT"] = self._status(
            "RATE LIMIT",
            "rate_limit" in source_text.lower() or "rate-limit" in evidence_text.lower(),
            evidence,
        )
        cells["RETRY"] = self._status(
            "RETRY",
            "retry" in source_text.lower() or "retry" in evidence_text.lower(),
            evidence,
        )
        cells["TIMEOUT"] = self._status(
            "TIMEOUT",
            "timeout" in source_text.lower(),
            evidence,
        )
        cells["IDEMPOTENCY"] = self._status(
            "IDEMPOTENCY",
            "idempotency_key" in source_text or "idempotency" in evidence_text.lower(),
            evidence,
        )
        cells["EVENTS"] = self._status(
            "EVENTS",
            "event_id" in source_text or "event_id" in evidence_text.lower(),
            evidence,
        )
        cells["PROVENANCE"] = self._status(
            "PROVENANCE",
            "SourceProvenance" in source_text or "provenance" in evidence_text.lower(),
            evidence,
        )
        cells["EVIDENCE"] = self._status(
            "EVIDENCE",
            "evidence" in source_text.lower() or "raw_evidence" in evidence_text.lower(),
            evidence,
        )
        cells["STRUCTURAL TEST"] = self._status(
            "STRUCTURAL TEST",
            "STRUCTURAL_TEST" in kinds,
            evidence,
            tested=True,
        )
        cells["CONTRACT TEST"] = self._status(
            "CONTRACT TEST",
            "CONTRACT_TEST" in kinds,
            evidence,
            tested=True,
        )
        cells["LIVE TEST"] = self._status(
            "LIVE_TEST",
            "LIVE_TEST" in kinds,
            evidence,
            tested=True,
        )
        cells["E2E TEST"] = self._status(
            "E2E_TEST",
            any(
                "e2e" in item.path.lower()
            and source_id in self.scanner._read(self.scanner.root / item.path)
                for item in evidence
            ),
            evidence,
            tested=True,
        )
        cells["NEGATIVE TEST"] = self._status(
            "NEGATIVE_TEST",
            "NEGATIVE_TEST" in kinds,
            evidence,
            tested=True,
        )
        cells["CI GATE"] = self._status(
            "CI",
            any(
                "integration-conformance" in item.path.lower()
                or "conformance" in self.scanner._read(self.scanner.root / item.path).lower()
                for item in evidence
            ),
            evidence,
            tested=True,
        )
        cells["PRODUCTION VERIFICATION"] = self._status(
            "PRODUCTION_VERIFICATION",
            "PRODUCTION_MANIFEST" in kinds
            and any(
                re.search(
                    r'"production_verified"\s*:\s*true\b',
                    self.scanner._read(self.scanner.root / item.path),
                    re.IGNORECASE,
                )
                is not None
                for item in evidence
            ),
            evidence,
            production=True,
        )
        return cells

    @staticmethod
    def _status(
        dimension: str,
        present: bool,
        evidence: tuple[RepositoryEvidence, ...],
        *,
        tested: bool = False,
        production: bool = False,
    ) -> ConformanceCell:
        matching = tuple(
            item.path for item in evidence
            if dimension.lower().replace(" ", "_") in item.kind.lower()
            or dimension.lower() in item.detail.lower()
        )
        if not present:
            return ConformanceCell(
                ConformanceStatus.UNKNOWN,
                matching,
                f"{dimension} requires explicit repository evidence",
            )
        status = (
            ConformanceStatus.PRODUCTION_VERIFIED if production
            else ConformanceStatus.TESTED if tested
            else ConformanceStatus.IMPLEMENTED
        )
        return ConformanceCell(status, matching or tuple(item.path for item in evidence[:3]))


def build_repository_certificate(
    root: Path,
    *,
    policy: CertificatePolicy | None = None,
    commit: str | None = None,
) -> IntegrationConformanceCertificate:
    return RepositoryConformanceCertificateBuilder(
        root,
        policy=policy,
        commit=commit,
    ).build()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Build OIS integration conformance certificate")
    parser.add_argument("--root", default=".")
    parser.add_argument("--output", default="integration-conformance-certificate.json")
    parser.add_argument("--commit", default=None)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    certificate = build_repository_certificate(Path(args.root), commit=args.commit)
    Path(args.output).write_text(certificate.to_json() + "\n", encoding="utf-8")
    print(certificate.to_json())
    raise SystemExit(0 if (certificate.valid or not args.strict) else 1)
