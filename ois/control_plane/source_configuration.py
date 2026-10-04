"""Tenant-scoped source configuration service for UI/API transports."""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
from typing import Any

from .source_policies import SourcePolicy, SourcePolicyStore


@dataclass(frozen=True)
class SourceConfiguration:
    tenant_id: str
    workspace_id: str
    source_id: str
    provider: str
    enabled: bool = True
    credential_id: str | None = None
    settings: dict[str, Any] | None = None


class SourceConfigurationService:
    """CRUD boundary; HTTP/UI transport remains outside the domain service."""

    def __init__(self, policies: SourcePolicyStore | None = None) -> None:
        self._policies = policies or SourcePolicyStore()
        self._configs: dict[tuple[str, str, str], SourceConfiguration] = {}
        self._lock = RLock()

    @property
    def policies(self) -> SourcePolicyStore:
        return self._policies

    def upsert(self, config: SourceConfiguration) -> SourceConfiguration:
        with self._lock:
            self._configs[(config.tenant_id, config.workspace_id, config.source_id)] = config
        try:
            existing = self._policies.get(
                config.tenant_id, config.workspace_id, config.source_id
            )
        except KeyError:
            existing = None
        self._policies.put(
            SourcePolicy(
                tenant_id=config.tenant_id,
                workspace_id=config.workspace_id,
                source_id=config.source_id,
                enabled=config.enabled,
                allowed_event_types=existing.allowed_event_types if existing else (),
                allowed_operations=existing.allowed_operations if existing else ("ingest",),
                require_credential=config.credential_id is not None,
            )
        )
        return config

    def get(self, tenant_id: str, workspace_id: str, source_id: str) -> SourceConfiguration:
        with self._lock:
            try:
                return self._configs[(tenant_id, workspace_id, source_id)]
            except KeyError as exc:
                raise KeyError(f"source configuration not found: {source_id}") from exc

    def list(self, tenant_id: str, workspace_id: str) -> tuple[SourceConfiguration, ...]:
        with self._lock:
            return tuple(
                sorted(
                    (
                        config for (t, w, _), config in self._configs.items()
                        if (t, w) == (tenant_id, workspace_id)
                    ),
                    key=lambda item: item.source_id,
                )
            )

    def disable(self, tenant_id: str, workspace_id: str, source_id: str) -> SourceConfiguration:
        config = self.get(tenant_id, workspace_id, source_id)
        disabled = SourceConfiguration(
            tenant_id=config.tenant_id,
            workspace_id=config.workspace_id,
            source_id=config.source_id,
            provider=config.provider,
            enabled=False,
            credential_id=config.credential_id,
            settings=config.settings,
        )
        return self.upsert(disabled)
