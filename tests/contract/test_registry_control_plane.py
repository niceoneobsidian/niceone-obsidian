"""Contract tests for the Registry Plane and Control Plane foundation."""

from __future__ import annotations

import pytest

from ois.control_plane import ControlPlane, ControlRequest
from ois.registries import CapabilityRegistry, Registry


def capability(payload: object) -> object:
    return payload


def test_registration_and_versioned_resolution() -> None:
    registry: Registry[object] = Registry()

    entry = registry.register("capability.example", "1.0.0", capability)

    assert entry.id == "capability.example"
    assert entry.version == "1.0.0"
    assert registry.resolve("capability.example", "1.0.0").value is capability


def test_version_isolation() -> None:
    registry: Registry[str] = Registry()
    registry.register("example", "1.0.0", "v1")
    registry.register("example", "2.0.0", "v2")

    assert registry.resolve("example", "1.0.0").value == "v1"
    assert registry.resolve("example", "2.0.0").value == "v2"


def test_duplicate_registration_is_rejected() -> None:
    registry: Registry[object] = Registry()
    registry.register("example", "1.0.0", capability)

    with pytest.raises(ValueError, match="already registered"):
        registry.register("example", "1.0.0", capability)


def test_snapshot_is_deterministic() -> None:
    first: Registry[str] = Registry()
    second: Registry[str] = Registry()

    for registry in (first, second):
        registry.register("zeta", "1.0.0", "z")
        registry.register("alpha", "2.0.0", "a")
        registry.register("alpha", "1.0.0", "a1")

    assert first.snapshot() == second.snapshot()
    assert [(entry.id, entry.version) for entry in first.snapshot()] == [
        ("alpha", "1.0.0"),
        ("alpha", "2.0.0"),
        ("zeta", "1.0.0"),
    ]


def test_control_plane_resolves_capability_through_registry() -> None:
    registry = CapabilityRegistry()
    registry.register("capability.example", "1.0.0", capability)
    control_plane = ControlPlane(capabilities=registry)

    resolved = control_plane.resolve_capability(
        ControlRequest("capability.example", "1.0.0"),
    )

    assert resolved is capability


def test_control_plane_rejects_invalid_capability() -> None:
    control_plane = ControlPlane()

    with pytest.raises(KeyError, match="not registered"):
        control_plane.resolve_capability(ControlRequest("missing.capability", "1.0.0"))


def test_control_plane_does_not_bypass_capability_registry() -> None:
    registry = CapabilityRegistry()
    control_plane = ControlPlane(capabilities=registry)

    with pytest.raises(KeyError, match="not registered"):
        control_plane.resolve_capability(ControlRequest("capability.example", "1.0.0"))

    registry.register("capability.example", "1.0.0", capability)

    assert control_plane.resolve_capability(
        ControlRequest("capability.example", "1.0.0"),
    ) is capability
