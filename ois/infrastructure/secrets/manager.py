"""General-purpose, fail-closed secret management API."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class SecretState(StrEnum):
    ACTIVE = "active"
    REVOKED = "revoked"


@dataclass(frozen=True)
class SecretMetadata:
    name: str
    provider: str
    environment: str
    required: bool = False
    scopes: tuple[str, ...] = ()
    rotation_days: int | None = None
    state: SecretState = SecretState.ACTIVE


class SecretProvider(Protocol):
    def get(self, name: str) -> str | None: ...
    def set(self, name: str, value: str) -> None: ...
    def delete(self, name: str) -> None: ...
    def exists(self, name: str) -> bool: ...


class SecretManager:
    """Single boundary through which OIS materializes secret values."""

    def __init__(
        self,
        provider: SecretProvider,
        metadata: dict[str, SecretMetadata] | None = None,
    ) -> None:
        self._provider = provider
        self._metadata = dict(metadata or {})

    def get(self, name: str) -> str | None:
        meta = self.metadata(name)
        if meta and meta.state is SecretState.REVOKED:
            raise PermissionError(f"secret is revoked: {name}")
        return self._provider.get(name)

    def require(self, name: str) -> str:
        value = self.get(name)
        if not value:
            raise KeyError(f"required secret is not configured: {name}")
        return value

    def optional(self, name: str) -> str | None:
        return self.get(name)

    def exists(self, name: str) -> bool:
        return bool(self.get(name))

    def metadata(self, name: str) -> SecretMetadata | None:
        return self._metadata.get(name)

    def validate(self, name: str) -> bool:
        meta = self.metadata(name)
        if meta and meta.required and meta.state is SecretState.REVOKED:
            return False
        return bool(self.get(name)) if meta and meta.required else True

    def health(self) -> dict[str, bool]:
        return {name: self.validate(name) for name in self._metadata}

    def registered_names(self) -> tuple[str, ...]:
        """Return registered secret names without exposing secret values."""
        return tuple(sorted(self._metadata))

    def register(self, metadata: SecretMetadata) -> None:
        if metadata.name in self._metadata:
            raise ValueError(f"secret already registered: {metadata.name}")
        self._metadata[metadata.name] = metadata

    def update_metadata(self, metadata: SecretMetadata) -> None:
        if metadata.name not in self._metadata:
            raise KeyError(f"secret is not registered: {metadata.name}")
        self._metadata[metadata.name] = metadata
