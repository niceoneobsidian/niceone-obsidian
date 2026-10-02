from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from .contracts import QualityGate, utc_now


@dataclass(frozen=True)
class Certificate:
    certificate_type: str
    subject: str
    version: str
    issued_at: datetime
    gates: tuple[QualityGate, ...]
    evidence_ids: tuple[str, ...] = ()
    production_verified: bool = False

    @property
    def valid(self) -> bool:
        return bool(self.evidence_ids) and bool(self.gates) and all(
            gate.passed for gate in self.gates
        )


@dataclass(frozen=True)
class ProductionReadinessCertificate:
    version: str
    certificates: tuple[Certificate, ...]
    issued_at: datetime = field(default_factory=utc_now)

    @property
    def production_verified(self) -> bool:
        return bool(self.certificates) and all(
            certificate.production_verified and certificate.valid
            for certificate in self.certificates
        )


def certify(
    certificate_type: str,
    subject: str,
    version: str,
    gates: list[QualityGate] | tuple[QualityGate, ...],
    *,
    evidence_ids: tuple[str, ...],
    production_verified: bool = False,
) -> Certificate:
    certificate = Certificate(
        certificate_type,
        subject,
        version,
        utc_now(),
        tuple(gates),
        evidence_ids,
        production_verified,
    )
    if not certificate.valid:
        raise ValueError("certificate gates/evidence are incomplete")
    return certificate
