from __future__ import annotations

import hashlib
import hmac
import json
import logging
import secrets
from typing import Any, TypedDict

import redis.asyncio as redis
from opentelemetry import metrics, trace
from opentelemetry.trace import Status, StatusCode
from psycopg_pool import AsyncConnectionPool

logger = logging.getLogger("ois.production_kernel")
tracer = trace.get_tracer("ois.kernel.core")
meter = metrics.get_meter("ois.kernel.core")
recovery_counter = meter.create_counter("ois_recovery_events_total")


class KernelPanicException(Exception):
    """Base exception for production-kernel failures."""


class TransientKernelFailure(KernelPanicException):
    """Raised for retryable transient failures."""


class ToolExecutionFailure(KernelPanicException):
    """Raised when a tool or external dependency fails."""


class ParameterValidationFailure(KernelPanicException):
    """Raised when execution input cannot be corrected automatically."""


class StateRecoveryFailure(KernelPanicException):
    """Raised when durable execution state requires recovery."""


class PermissionDenied(KernelPanicException):
    """Raised when policy or authorization denies an operation."""


class SafetyViolation(KernelPanicException):
    """Raised when a safety gate requires execution to stop."""


class FencingTokenMismatch(KernelPanicException):
    """Raised when a stale fencing token or side-effect hash is detected."""


class EvidenceVerificationFailure(KernelPanicException):
    """Raised when evidence or promotion verification fails."""


class WorkflowState(TypedDict, total=False):
    tenant_id: str
    thread_id: str
    workflow_version: str
    current_state: str
    execution_plan: list[str]
    proposed_side_effect: dict[str, Any]
    side_effect_hash: str
    resolution: str
    fencing_token: int


class FencedLease:
    RELEASE = """
    if redis.call('get',KEYS[1]) == ARGV[1]
    then return redis.call('del',KEYS[1])
    else return 0
    end
    """

    def __init__(self, client: redis.Redis, key: str, ttl_ms: int = 15000) -> None:
        self.client = client
        self.key = key
        self.ttl_ms = ttl_ms
        self.owner = secrets.token_hex(16)
        self.token: int | None = None

    async def acquire(self) -> int:
        token = int(await self.client.incr(f"{self.key}:counter"))
        value = f"{token}:{self.owner}"
        acquired = await self.client.set(
            self.key,
            value,
            px=self.ttl_ms,
            nx=True,
        )
        if not acquired:
            raise KernelPanicException("Execution lease contention")
        self.token = token
        return token

    async def release(self) -> None:
        if self.token is None:
            return
        await self.client.eval(
            self.RELEASE,
            1,
            self.key,
            f"{self.token}:{self.owner}",
        )


class EvidenceLedger:
    def __init__(self, pool: AsyncConnectionPool, signing_key: bytes) -> None:
        self.pool = pool
        self.signing_key = signing_key

    def sign(self, message: str) -> str:
        return hmac.new(
            self.signing_key,
            message.encode(),
            hashlib.sha256,
        ).hexdigest()

    async def append(
        self,
        tenant_id: str,
        thread_id: str,
        event_type: str,
        payload_hash: str,
        context: dict[str, Any],
    ) -> str:
        context_json = json.dumps(
            context,
            sort_keys=True,
            separators=(",", ":"),
        )
        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT set_config('app.current_tenant_id', %s, true)",
                    (tenant_id,),
                )
                await cur.execute(
                    "SELECT pg_advisory_xact_lock(hashtext(%s))",
                    (f"{tenant_id}:{thread_id}",),
                )
                await cur.execute(
                    """
                    SELECT
                        COALESCE(MAX(sequence_no), 0),
                        COALESCE(
                            (
                                SELECT event_hash
                                FROM ois_attestation_evidence
                                WHERE tenant_id = %s
                                  AND thread_id = %s
                                ORDER BY sequence_no DESC
                                LIMIT 1
                            ),
                            repeat('0', 64)
                        )
                    FROM ois_attestation_evidence
                    WHERE tenant_id = %s
                      AND thread_id = %s
                    """,
                    (tenant_id, thread_id, tenant_id, thread_id),
                )
                row = await cur.fetchone()
                if row is None:
                    raise RuntimeError("failed to allocate evidence sequence")
                sequence_no, previous_hash = row
                sequence = int(sequence_no) + 1
                event_hash = hashlib.sha256(
                    f"{tenant_id}:{thread_id}:{sequence}:{event_type}:"
                    f"{payload_hash}:{previous_hash}:{context_json}".encode()
                ).hexdigest()
                signature = self.sign(
                    f"{tenant_id}:{thread_id}:{sequence}:{event_type}:"
                    f"{payload_hash}:{previous_hash}:{event_hash}"
                )
                await cur.execute(
                    """
                    INSERT INTO ois_attestation_evidence (
                        tenant_id,
                        thread_id,
                        sequence_no,
                        event_type,
                        payload_hash,
                        previous_hash,
                        event_hash,
                        context_snapshot,
                        attestation_signature
                    )
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    RETURNING evidence_id
                    """,
                    (
                        tenant_id,
                        thread_id,
                        sequence,
                        event_type,
                        payload_hash,
                        previous_hash,
                        event_hash,
                        context_json,
                        signature,
                    ),
                )
                inserted = await cur.fetchone()
                if inserted is None:
                    raise RuntimeError("evidence insert returned no identifier")
                await conn.commit()
                return str(inserted[0])


class OISProductionSupervisor:
    def __init__(
        self,
        db_pool: AsyncConnectionPool,
        redis_client: redis.Redis,
        signing_key: bytes,
    ) -> None:
        self.pool = db_pool
        self.redis = redis_client
        self.secret = signing_key
        self.evidence = EvidenceLedger(db_pool, signing_key)

    def _sign_hash(self, content: str) -> str:
        return hmac.new(
            self.secret,
            content.encode(),
            hashlib.sha256,
        ).hexdigest()

    @staticmethod
    def canonical_manifest_hash(manifest: dict[str, Any]) -> str:
        encoded = json.dumps(
            manifest,
            sort_keys=True,
            separators=(",", ":"),
        ).encode()
        return hashlib.sha256(encoded).hexdigest()

    async def verify_artifact_promotion_gate(
        self,
        tenant_id: str,
        workflow_name: str,
        version_tag: str,
    ) -> dict[str, Any]:
        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT set_config('app.current_tenant_id', %s, true)",
                    (tenant_id,),
                )
                await cur.execute(
                    """
                    SELECT
                        manifest_payload,
                        provenance_hash,
                        supervisor_promotion_signature
                    FROM ois_artifact_registry
                    WHERE tenant_id = %s
                      AND workflow_name = %s
                      AND version_tag = %s
                    """,
                    (tenant_id, workflow_name, version_tag),
                )
                record = await cur.fetchone()

        if not record:
            raise EvidenceVerificationFailure(
                "Promotion denied: no signed artifact attestation"
            )

        manifest, provenance_hash, signature = record
        actual_hash = self.canonical_manifest_hash(manifest)
        if not hmac.compare_digest(actual_hash, provenance_hash):
            raise EvidenceVerificationFailure(
                "Promotion denied: manifest does not match provenance hash"
            )

        expected = self._sign_hash(
            f"{tenant_id}:{workflow_name}:{version_tag}:{provenance_hash}"
        )
        if not hmac.compare_digest(expected, signature):
            raise EvidenceVerificationFailure(
                "Registry artifact signature mismatch"
            )
        return manifest

    @staticmethod
    def classify_failure(exc: Exception) -> str:
        if isinstance(exc, FencingTokenMismatch):
            return "RC-08"
        if isinstance(exc, EvidenceVerificationFailure):
            return "RC-12"
        if isinstance(exc, SafetyViolation):
            return "RC-11"
        if isinstance(exc, PermissionError | PermissionDenied):
            return "RC-12"
        if isinstance(exc, StateRecoveryFailure):
            return "RC-06"
        if isinstance(exc, ToolExecutionFailure):
            return "RC-03"
        if isinstance(exc, ParameterValidationFailure | ValueError):
            return "RC-04"
        if isinstance(exc, TimeoutError | TransientKernelFailure):
            return "RC-01"
        return "RC-09"

    async def execute_supervisor_pipeline(
        self,
        tenant_id: str,
        thread_id: str,
        workflow_name: str,
        version: str,
        client_input: dict[str, Any],
    ) -> dict[str, Any]:
        with tracer.start_as_current_span(
            "supervisor_pipeline",
            attributes={"tenant_id": tenant_id, "thread_id": thread_id},
        ) as span:
            lease = FencedLease(
                self.redis,
                f"lock:lease:execution:{tenant_id}:{thread_id}",
            )
            state: WorkflowState = {
                "tenant_id": tenant_id,
                "thread_id": thread_id,
                "workflow_version": version,
                "current_state": "EXECUTION",
                "execution_plan": [],
                "proposed_side_effect": {},
                "side_effect_hash": "",
                "resolution": "PENDING",
            }
            lease_acquired = False
            try:
                manifest = await self.verify_artifact_promotion_gate(
                    tenant_id,
                    workflow_name,
                    version,
                )
                state["execution_plan"] = manifest.get(
                    "routing_dag",
                    ["evaluate_step", "apply_step"],
                )
                state["fencing_token"] = await lease.acquire()
                lease_acquired = True

                from langgraph.graph import END, START, StateGraph

                async def evaluate_step(
                    current: WorkflowState,
                ) -> dict[str, Any]:
                    payload = client_input.get(
                        "proposed_side_effect",
                        {"action": "noop"},
                    )
                    digest = hashlib.sha256(
                        json.dumps(
                            payload,
                            sort_keys=True,
                            separators=(",", ":"),
                        ).encode()
                    ).hexdigest()
                    return {
                        "current_state": "APPROVAL_REQUIRED",
                        "proposed_side_effect": payload,
                        "side_effect_hash": digest,
                    }

                async def apply_step(
                    current: WorkflowState,
                ) -> dict[str, Any]:
                    if current.get("resolution") != "APPROVED":
                        return {"current_state": "ABORT"}
                    digest = hashlib.sha256(
                        json.dumps(
                            current["proposed_side_effect"],
                            sort_keys=True,
                            separators=(",", ":"),
                        ).encode()
                    ).hexdigest()
                    if not hmac.compare_digest(
                        digest,
                        current["side_effect_hash"],
                    ):
                        raise FencingTokenMismatch(
                            "Side-effect hash changed after approval"
                        )
                    return {"current_state": "RESUME"}

                builder = StateGraph(WorkflowState)
                builder.add_node("evaluate_step", evaluate_step)
                builder.add_node("apply_step", apply_step)
                builder.add_edge(START, "evaluate_step")
                builder.add_edge("evaluate_step", "apply_step")
                builder.add_edge("apply_step", END)
                kernel = builder.compile(interrupt_before=["apply_step"])
                result = await kernel.ainvoke(
                    state,
                    config={"configurable": {"thread_id": thread_id}},
                )
                if not isinstance(result, dict):
                    raise StateRecoveryFailure(
                        "LangGraph returned an invalid state"
                    )

                result_state = dict(result)
                result_state["fencing_token"] = state["fencing_token"]
                await self.evidence.append(
                    tenant_id,
                    thread_id,
                    "KERNEL_INTERRUPT_WAITING",
                    str(result_state.get("side_effect_hash", "")),
                    {
                        "status": "HALTED",
                        "fencing_token": state["fencing_token"],
                        "current_state": result_state.get("current_state"),
                    },
                )
                return {
                    "status": "WAITING_FOR_HUMAN",
                    "thread_id": thread_id,
                    "fencing_token": state["fencing_token"],
                    "state": result_state,
                }
            except Exception as exc:
                span.record_exception(exc)
                span.set_status(Status(StatusCode.ERROR, str(exc)))
                await self.execute_12_case_recovery_matrix(
                    tenant_id,
                    thread_id,
                    self.classify_failure(exc),
                    str(exc),
                    state,
                )
                raise
            finally:
                if lease_acquired:
                    await lease.release()

    async def execute_12_case_recovery_matrix(
        self,
        tenant_id: str,
        thread_id: str,
        scenario_id: str,
        diagnostic_log: str,
        state_dump: dict[str, Any],
    ) -> None:
        recovery_counter.add(1, {"scenario": scenario_id})
        serialized = json.dumps(
            state_dump,
            sort_keys=True,
            default=str,
        )
        payload_hash = hashlib.sha256(
            f"{serialized}:{diagnostic_log}".encode()
        ).hexdigest()
        signature = self._sign_hash(
            f"{tenant_id}:{thread_id}:{scenario_id}:{payload_hash}"
        )
        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT set_config('app.current_tenant_id', %s, true)",
                    (tenant_id,),
                )
                await cur.execute(
                    """
                    INSERT INTO ois_kernel_dead_letter_queue (
                        tenant_id,
                        thread_id,
                        last_scenario_id,
                        error_diagnostic_log,
                        frozen_context_data,
                        cryptographic_seal_signature
                    )
                    VALUES (%s,%s,%s,%s,%s,%s)
                    """,
                    (
                        tenant_id,
                        thread_id,
                        scenario_id,
                        diagnostic_log,
                        serialized,
                        signature,
                    ),
                )
                await conn.commit()
