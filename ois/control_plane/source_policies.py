"""Authoritative source policies for the OIS control plane."""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock


@dataclass(frozen=True)
class SourcePolicy:
    tenant_id: str
    workspace_id: str
    source_id: str
    enabled: bool = True
    allowed_event_types: tuple[str, ...] = ()
    allowed_operations: tuple[str, ...] = ("ingest",)
    require_credential: bool = True

    def allows(self, *, operation: str, event_type: str | None = None) -> bool:
        if not self.enabled or operation not in self.allowed_operations:
            return False
        return not self.allowed_event_types or event_type in self.allowed_event_types


class SourcePolicyStore:
    """Thread-safe source policy store."""

    def __init__(self) -> None:
        self._policies: dict[tuple[str, str, str], SourcePolicy] = {}
        self._lock = RLock()

    def put(self, policy: SourcePolicy) -> None:
        with self._lock:
            self._policies[(policy.tenant_id, policy.workspace_id, policy.source_id)] = policy

    def get(self, tenant_id: str, workspace_id: str, source_id: str) -> SourcePolicy:
        with self._lock:
            try:
                return self._policies[(tenant_id, workspace_id, source_id)]
            except KeyError as exc:
                raise KeyError(f"source policy not configured: {source_id}") from exc

    def authorize(
        self,
        tenant_id: str,
        workspace_id: str,
        source_id: str,
        *,
        operation: str = "ingest",
        event_type: str | None = None,
        credential_present: bool = False,
    ) -> SourcePolicy:
        policy = self.get(tenant_id, workspace_id, source_id)
        if policy.require_credential and not credential_present:
            raise PermissionError("source policy requires a credential")
        if not policy.allows(operation=operation, event_type=event_type):
            raise PermissionError("source operation denied by control-plane policy")
        return policy

    def list(self, tenant_id: str, workspace_id: str) -> tuple[SourcePolicy, ...]:
        with self._lock:
            return tuple(
                sorted(
                    (
                        policy
                        for (t, w, _), policy in self._policies.items()
                        if (t, w) == (tenant_id, workspace_id)
                    ),
                    key=lambda item: item.source_id,
                )
            )
