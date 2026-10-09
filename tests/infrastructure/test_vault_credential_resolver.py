from __future__ import annotations

import pytest

from ois.infrastructure.source_gateway.credentials import CredentialRef, TenantScope
from ois.infrastructure.source_gateway.secret_manager import (
    CredentialBinding,
    CredentialConformanceAdapter,
    VaultCredentialResolver,
)
from ois.integration.credential_conformance import assert_credential_resolver_conformance


class FakeSecretBackend:
    def __init__(self, values: dict[tuple[str, str], str | None]) -> None:
        self.values = values
        self.reads: list[tuple[str, str]] = []

    def get(self, path: str, key: str) -> str | None:
        self.reads.append((path, key))
        return self.values.get((path, key))


@pytest.fixture
def binding() -> CredentialBinding:
    return CredentialBinding(
        credential_id="cred-a",
        tenant_id="tenant-a",
        workspace_id="workspace-a",
        provider="github",
        vault_path="secret/data/ois/tenant-a/github",
        vault_key="token",
    )


def test_resolves_registered_credential_for_matching_scope(binding: CredentialBinding) -> None:
    backend = FakeSecretBackend({(binding.vault_path, binding.vault_key): "secret-value"})
    resolver = VaultCredentialResolver(backend, [binding])

    value = resolver.resolve(
        CredentialRef("cred-a", "tenant-a", "github"),
        TenantScope("tenant-a", "workspace-a"),
    )

    assert value == "secret-value"
    assert backend.reads == [(binding.vault_path, binding.vault_key)]


@pytest.mark.parametrize(
    ("ref", "scope"),
    [
        (CredentialRef("cred-a", "tenant-b", "github"), TenantScope("tenant-a", "workspace-a")),
        (CredentialRef("cred-a", "tenant-a", "github"), TenantScope("tenant-a", "workspace-b")),
        (CredentialRef("cred-a", "tenant-a", "gitlab"), TenantScope("tenant-a", "workspace-a")),
    ],
)
def test_rejects_scope_or_provider_mismatch_before_backend_read(
    binding: CredentialBinding,
    ref: CredentialRef,
    scope: TenantScope,
) -> None:
    backend = FakeSecretBackend({(binding.vault_path, binding.vault_key): "secret-value"})
    resolver = VaultCredentialResolver(backend, [binding])

    with pytest.raises(PermissionError):
        resolver.resolve(ref, scope)

    assert backend.reads == []


def test_rejects_unknown_credential_without_disclosing_secret(
    binding: CredentialBinding,
) -> None:
    backend = FakeSecretBackend({(binding.vault_path, binding.vault_key): "secret-value"})
    resolver = VaultCredentialResolver(backend, [binding])

    with pytest.raises(KeyError) as error:
        resolver.resolve(
            CredentialRef("unknown", "tenant-a", "github"),
            TenantScope("tenant-a", "workspace-a"),
        )

    assert "secret-value" not in str(error.value)
    assert backend.reads == []


def test_revoked_credential_is_denied_before_backend_read(binding: CredentialBinding) -> None:
    backend = FakeSecretBackend({(binding.vault_path, binding.vault_key): "secret-value"})
    resolver = VaultCredentialResolver(backend, [binding])
    resolver.revoke("cred-a")

    with pytest.raises(PermissionError, match="revoked"):
        resolver.resolve(
            CredentialRef("cred-a", "tenant-a", "github"),
            TenantScope("tenant-a", "workspace-a"),
        )

    assert backend.reads == []


def test_empty_secret_material_fails_closed(binding: CredentialBinding) -> None:
    backend = FakeSecretBackend({(binding.vault_path, binding.vault_key): ""})
    resolver = VaultCredentialResolver(backend, [binding])

    with pytest.raises(PermissionError, match="unavailable"):
        resolver.resolve(
            CredentialRef("cred-a", "tenant-a", "github"),
            TenantScope("tenant-a", "workspace-a"),
        )


def test_conformance_adapter_satisfies_existing_keyword_contract() -> None:
    binding = CredentialBinding(
        credential_id="cred-a",
        tenant_id="tenant-a",
        workspace_id="workspace-a",
        provider="github",
        vault_path="secret/data/ois/tenant-a/github",
        vault_key="token",
    )
    backend = FakeSecretBackend({(binding.vault_path, binding.vault_key): "secret-value"})
    resolver = VaultCredentialResolver(backend, [binding])

    proof = assert_credential_resolver_conformance(CredentialConformanceAdapter(resolver))

    assert proof.resolved
    assert proof.cross_tenant_blocked


def test_duplicate_credential_bindings_are_rejected(binding: CredentialBinding) -> None:
    backend = FakeSecretBackend({})
    with pytest.raises(ValueError, match="duplicate"):
        VaultCredentialResolver(backend, [binding, binding])
