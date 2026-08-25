"""Tenant isolation contracts."""

from dataclasses import dataclass


@dataclass(frozen=True)
class TenantScope:
    tenant_id: str
    resource_scope: str
