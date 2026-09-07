from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from ois.kernel.attestation import AttestationPayload, EvidenceLedgerSigner


class HITLError(RuntimeError):
    """Base human-admission error."""


class HITLNotFound(HITLError):
    """Raised when a gate is absent or outside the caller tenant."""


class HITLAuthorizationError(HITLError):
    """Raised when the principal lacks the required role."""


@dataclass(frozen=True)
class Principal:
    user_id: str
    tenant_id: str
    roles: frozenset[str]


@dataclass(frozen=True)
class GateResolution:
    gate_id: str
    execution_id: str
    decision: str
    signature: str
    resolved_at: datetime


class HITLAdmissionService:
    """Atomically resolve a tenant-scoped approval gate and append evidence.

    The connection factory must return a fresh psycopg connection. The service
    deliberately uses PostgreSQL ``set_config`` rather than interpolating tenant
    values into SQL, and locks the gate row before authorization/mutation.
    """

    def __init__(self, connection_factory: Callable[[], object]) -> None:
        self._connection_factory = connection_factory

    def resolve(
        self,
        *,
        gate_id: str,
        principal: Principal,
        decision: str,
    ) -> GateResolution:
        if decision not in {"APPROVED", "REJECTED"}:
            raise ValueError("decision must be APPROVED or REJECTED")

        with self._connection_factory() as connection:
            with connection.cursor() as cursor:
                cursor.execute(
                    "SELECT set_config('app.current_tenant_id', %s, true)",
                    (principal.tenant_id,),
                )
                cursor.execute(
                    """
                    SELECT execution_id, workflow_version, required_role,
                           side_effect_hash, resolution
                    FROM ois_hitl_gates
                    WHERE gate_id = %s
                    FOR UPDATE
                    """,
                    (gate_id,),
                )
                row = cursor.fetchone()
                if row is None:
                    raise HITLNotFound("HITL gate does not exist in the tenant scope")

                execution_id, workflow_version, required_role, side_effect_hash, current = row
                if current != "PENDING":
                    raise HITLError("HITL gate is already resolved")
                if required_role not in principal.roles:
                    raise HITLAuthorizationError("principal lacks the required role")

                payload = AttestationPayload(
                    tenant_id=principal.tenant_id,
                    execution_id=str(execution_id),
                    gate_id=gate_id,
                    decision=decision,
                    side_effect_hash=side_effect_hash,
                    workflow_version=workflow_version,
                )
                signature = EvidenceLedgerSigner.sign(payload)
                resolved_at = datetime.now(UTC)
                cursor.execute(
                    """
                    UPDATE ois_hitl_gates
                    SET resolution = %s, resolved_by = %s,
                        resolved_at = %s, supervisor_signature = %s
                    WHERE gate_id = %s AND resolution = 'PENDING'
                    """,
                    (decision, principal.user_id, resolved_at, signature, gate_id),
                )
                if cursor.rowcount != 1:
                    raise HITLError("HITL gate changed concurrently")

                cursor.execute(
                    """
                    INSERT INTO ois_attestation_evidence
                    (tenant_id, execution_id, gate_id, event_type, payload_hash,
                     context_snapshot, attestation_signature, created_at)
                    VALUES (%s, %s, %s, 'HUMAN_ADMISSION_DECISION', %s, %s, %s, %s)
                    """,
                    (
                        principal.tenant_id,
                        execution_id,
                        gate_id,
                        side_effect_hash,
                        json.dumps(
                            {"actor": principal.user_id, "decision": decision},
                            sort_keys=True,
                        ),
                        signature,
                        resolved_at,
                    ),
                )
                connection.commit()
                return GateResolution(
                    gate_id=gate_id,
                    execution_id=str(execution_id),
                    decision=decision,
                    signature=signature,
                    resolved_at=resolved_at,
                )
