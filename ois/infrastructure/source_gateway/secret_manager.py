"""Vault-backed credential resolution with explicit tenant/workspace bindings.

The registry contains metadata only; secret values remain in the configured backend.
This first adapter keeps revocation state in-process and deliberately does not cache
resolved secret values.
"""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Protocol

from .credentials import CredentialRef, TenantScope


class SecretBackend(Protocol):
    """Minimal read contract implemented by VaultKV2Backend."""

    def get(self, path: str, key: str) -> str | None: ...


@dataclass(frozen=True)
class CredentialBinding:
    """Non-secret metadata that binds a credential to its authorized scope."""

    credential_id: str
    tenant_id: str
    workspace_id: str
    provider: str
    vault_path: str
    vault_key: str

    def __post_init__(self) -> None:
        if not all(
            (
                self.credential_id,
                self.tenant_id,
                self.workspace_id,
                self.provider,
                self.vault_path,
                self.vault_key,
            )
        ):
            raise ValueError("credential binding fields must be non-empty")


class VaultCredentialResolver:
    """Resolve only registered credentials whose tenant, workspace and provider match."""

    def __init__(
        self,
        backend: SecretBackend,
        bindings: tuple[CredentialBinding, ...] | list[CredentialBinding],
    ) -> None:
        self._backend = backend
        self._bindings: dict[str, CredentialBinding] = {}
        for binding in bindings:
            if binding.credential_id in self._bindings:
                raise ValueError("duplicate credential binding")
            self._bindings[binding.credential_id] = binding
        self._revoked: set[str] = set()
        self._lock = RLock()

    def revoke(self, credential_id: str) -> None:
        """Deny future resolutions of a registered credential in this process."""
        with self._lock:
            if credential_id not in self._bindings:
                raise KeyError("credential is not registered")
            self._revoked.add(credential_id)

    def resolve(self, ref: CredentialRef, scope: TenantScope) -> str:
        """Resolve a Source Gateway credential reference."""
        if ref.tenant_id != scope.tenant_id:
            raise PermissionError("credential is outside the tenant scope")
        with self._lock:
            binding = self._bindings.get(ref.credential_id)
            if binding is None:
                raise KeyError("credential is not registered")
            self._authorize(binding, ref.tenant_id, scope.workspace_id, ref.provider)
            if ref.credential_id in self._revoked:
                raise PermissionError("credential is revoked")
            value = self._backend.get(binding.vault_path, binding.vault_key)
        if not value:
            raise PermissionError("credential material is unavailable")
        return value

    def resolve_by_identity(
        self, *, tenant_id: str, workspace_id: str, credential_id: str
    ) -> str:
        """Resolve using the integration-conformance keyword contract."""
        with self._lock:
            binding = self._bindings.get(credential_id)
            if binding is None:
                raise KeyError("credential is not registered")
            self._authorize(binding, tenant_id, workspace_id, binding.provider)
            if credential_id in self._revoked:
                raise PermissionError("credential is revoked")
            value = self._backend.get(binding.vault_path, binding.vault_key)
        if not value:
            raise PermissionError("credential material is unavailable")
        return value

    @staticmethod
    def _authorize(
        binding: CredentialBinding,
        tenant_id: str,
        workspace_id: str,
        provider: str,
    ) -> None:
        if binding.tenant_id != tenant_id:
            raise PermissionError("credential is outside the tenant scope")
        if binding.workspace_id != workspace_id:
            raise PermissionError("credential is outside the workspace scope")
        if binding.provider != provider:
            raise PermissionError("credential provider does not match")


class CredentialConformanceAdapter:
    """Expose the existing keyword-based conformance contract for a resolver."""

    def __init__(self, resolver: VaultCredentialResolver) -> None:
        self._resolver = resolver

    def resolve(self, *, tenant_id: str, workspace_id: str, credential_id: str) -> object:
        return self._resolver.resolve_by_identity(
            tenant_id=tenant_id,
            workspace_id=workspace_id,
            credential_id=credential_id,
        )
