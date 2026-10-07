from __future__ import annotations

from ois.infrastructure.source_adapters.bootstrap import (
    build_application_source_adapter_registry,
)


def test_phase_a_source_adapters_are_canonical_registry_contracts() -> None:
    registry = build_application_source_adapter_registry()

    github = registry.spec("github.rest.user")
    google = registry.spec("google.drive.files")
    meta = registry.spec("meta.graph.me")

    assert github.protocol == "rest"
    assert github.version == "v3"
    assert github.capabilities == ("github.user", "evidence.raw")

    assert google.protocol == "rest"
    assert google.version == "v3"
    assert google.capabilities == ("google.drive.files", "evidence.raw")

    assert meta.protocol == "rest"
    assert meta.version == "v24.0"
    assert meta.capabilities == ("meta.graph.me", "evidence.raw")
