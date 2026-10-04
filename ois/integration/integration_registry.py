"""Governed external integration registry."""
from __future__ import annotations
from dataclasses import dataclass
from typing import Protocol

class IntegrationError(RuntimeError): pass

@dataclass(frozen=True)
class IntegrationSpec:
    integration_id: str
    provider: str
    base_url: str
    enabled: bool = False
    supports_read: bool = True
    supports_write: bool = False
    credential_ref: str | None = None
    scopes: tuple[str, ...] = ()
    timeout_ms: int = 30000
    max_retries: int = 3

class IntegrationAdapter(Protocol):
    def health_check(self) -> bool: ...
    def request(self, method: str, path: str, **kwargs: object) -> object: ...

class IntegrationRegistry:
    def __init__(self) -> None:
        self._items: dict[str, IntegrationSpec] = {}
    def register(self, spec: IntegrationSpec) -> None:
        if spec.integration_id in self._items: raise IntegrationError(f"integration already registered: {spec.integration_id}")
        if spec.supports_write and not spec.credential_ref:
            raise IntegrationError(f"write-capable integration requires credential_ref: {spec.integration_id}")
        self._items[spec.integration_id] = spec
    def get(self, integration_id: str) -> IntegrationSpec:
        try: return self._items[integration_id]
        except KeyError as exc: raise IntegrationError(f"integration not registered: {integration_id}") from exc
    def enabled(self) -> tuple[IntegrationSpec, ...]:
        return tuple(item for item in self._items.values() if item.enabled)
    def all(self) -> tuple[IntegrationSpec, ...]:
        return tuple(self._items.values())
