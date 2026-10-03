from __future__ import annotations

import pytest

from ois.platform import (
    EvidenceStore,
    OISControlPlane,
    ProductionReadinessCertificate,
    SourceRegistry,
)
from ois.platform.certification import certify
from ois.platform.contracts import PlatformIdentity, QualityGate, VersionRef
from ois.platform.evolution import EvolutionRegistry, EvolutionState


class Adapter:
    source_id = "test.live"

    def health(self) -> bool:
        return True

    def collect(self, identity: PlatformIdentity, **kwargs: object) -> list[object]:
        return []


def test_source_registry() -> None:
    registry = SourceRegistry()
    registry.register(Adapter())
    assert registry.snapshot() == ("test.live",)
    assert registry.healthy() == ("test.live",)


def test_evidence_tenant_boundary() -> None:
    store = EvidenceStore()
    artifact = store.append(PlatformIdentity("a"), "source", {"x": 1})
    assert store.verify(artifact.evidence_id)
    with pytest.raises(PermissionError):
        store.append(
            PlatformIdentity("b"),
            "derived",
            {},
            parent_ids=(artifact.evidence_id,),
        )


def test_learning_requires_evidence() -> None:
    from ois.platform.learning import LearningStore

    with pytest.raises(ValueError):
        LearningStore().record(
            PlatformIdentity("t"),
            "h",
            evidence_ids=(),
            outcome_ids=(),
            confidence=0.5,
        )


def test_evolution_gates() -> None:
    registry = EvolutionRegistry()
    candidate = registry.propose(
        VersionRef("prompt", "1"),
        {"x": 1},
        evidence_ids=("e",),
    )
    with pytest.raises(PermissionError):
        registry.promote(candidate.candidate_id)
    candidate = registry.evaluate(candidate.candidate_id, True)
    candidate = registry.approve(candidate.candidate_id)
    candidate = registry.promote(candidate.candidate_id)
    assert candidate.state is EvolutionState.PROMOTED


def test_readiness_defaults_fail_closed() -> None:
    control_plane = OISControlPlane.create()
    certificate = certify(
        "EvidenceIntegrityCertificate",
        "evidence",
        "1",
        [QualityGate("hash", True)],
        evidence_ids=("e",),
        production_verified=False,
    )
    control_plane.attest(PlatformIdentity("t"), certificate)
    readiness = control_plane.readiness((certificate,), "1")
    assert isinstance(readiness, ProductionReadinessCertificate)
    assert not readiness.production_verified
