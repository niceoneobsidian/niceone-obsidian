from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import logging
import random
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Awaitable, Callable

import psycopg
import redis.asyncio as redis
from opentelemetry import metrics
from psycopg_pool import AsyncConnectionPool

logger = logging.getLogger("ois.kernel.production_resilience")

meter = metrics.get_meter("ois.kernel.core")
recovery_counter = meter.create_counter("ois_recovery_events_total", unit="1")
dlq_counter = meter.create_counter("ois_dlq_evacuations_total", unit="1")
lease_collision_counter = meter.create_counter("ois_lease_collisions_total", unit="1")


class KernelPanicException(RuntimeError):
    """Safety boundary violation: execution must fail closed."""


class FencingTokenMismatch(KernelPanicException):
    """The worker no longer owns the valid lease."""


class LeaseAcquisitionFailed(KernelPanicException):
    """Another worker currently owns the lease."""


class RetryExhaustedException(KernelPanicException):
    """A transient operation exceeded its bounded retry/deadline budget."""


class RecoverySinkUnavailable(KernelPanicException):
    """The durable recovery sink is unavailable; execution must remain isolated."""


@dataclass(frozen=True, slots=True)
class KernelTaskContext:
    tenant_id: str
    thread_id: str
    workflow_version: str
    max_retries: int = 3
    base_backoff_s: float = 0.25
    max_backoff_s: float = 10.0
    retry_deadline_s: float = 60.0


@dataclass(frozen=True, slots=True)
class Lease:
    key: str
    owner_nonce: str
    fencing_token: int
    ttl_ms: int


ACQUIRE_LUA = """
local key = KEYS[1]
if redis.call('EXISTS', key) == 1 then return {0, 0} end
local sequence_key = key .. ':sequence'
local token = redis.call('INCR', sequence_key)
redis.call('HSET', key, 'owner_nonce', ARGV[1], 'fencing_token', token)
redis.call('PEXPIRE', key, ARGV[2])
return {1, token}
"""

RENEW_LUA = """
local key = KEYS[1]
if redis.call('HGET', key, 'owner_nonce') ~= ARGV[1] then return 0 end
return redis.call('PEXPIRE', key, ARGV[2])
"""

RELEASE_LUA = """
local key = KEYS[1]
if redis.call('HGET', key, 'owner_nonce') ~= ARGV[1] then return 0 end
return redis.call('DEL', key)
"""

READ_LEASE_LUA = """
local nonce = redis.call('HGET', KEYS[1], 'owner_nonce')
local token = redis.call('HGET', KEYS[1], 'fencing_token')
if not nonce or not token then return {0, '', 0} end
return {1, nonce, token}
"""


class FencedLeaseManager:
    """Redis lease with owner nonce plus monotonic fencing token."""

    def __init__(self, client: redis.Redis, ttl_ms: int = 10_000) -> None:
        if ttl_ms < 100:
            raise ValueError("ttl_ms must be at least 100ms")
        self.client = client
        self.ttl_ms = ttl_ms

    async def acquire(self, key: str) -> Lease:
        nonce = secrets.token_hex(32)
        result = await self.client.eval(ACQUIRE_LUA, 1, key, nonce, self.ttl_ms)
        if int(result[0]) != 1:
            raise LeaseAcquisitionFailed(f"RC-05 lease is already held: {key}")
        return Lease(key, nonce, int(result[1]), self.ttl_ms)

    async def renew(self, lease: Lease) -> None:
        result = await self.client.eval(RENEW_LUA, 1, lease.key, lease.owner_nonce, lease.ttl_ms)
        if int(result) != 1:
            raise FencingTokenMismatch("RC-05 lease renewal rejected: ownership lost")

    async def assert_current(self, lease: Lease) -> None:
        result = await self.client.eval(READ_LEASE_LUA, 1, lease.key)
        if int(result[0]) != 1:
            raise FencingTokenMismatch("RC-05 lease no longer exists")
        current_nonce = result[1].decode("utf-8") if isinstance(result[1], bytes) else str(result[1])
        if current_nonce != lease.owner_nonce:
            raise FencingTokenMismatch("RC-05 lease is no longer owned by this worker")
        if int(result[2]) != lease.fencing_token:
            raise FencingTokenMismatch("RC-05 fencing token changed")

    async def release(self, lease: Lease) -> None:
        await self.client.eval(RELEASE_LUA, 1, lease.key, lease.owner_nonce)


class LeaseHeartbeat:
    """Renews a lease before expiry and surfaces ownership loss to the caller."""

    def __init__(self, manager: FencedLeaseManager, lease: Lease) -> None:
        self.manager = manager
        self.lease = lease
        self.lost = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    async def __aenter__(self) -> LeaseHeartbeat:
        self._task = asyncio.create_task(self._run())
        return self

    async def __aexit__(self, exc_type: Any, exc: Any, tb: Any) -> None:
        if self._task is not None:
            self._task.cancel()
            await asyncio.gather(self._task, return_exceptions=True)

    async def _run(self) -> None:
        interval = max(self.lease.ttl_ms / 3000.0, 0.1)
        try:
            while True:
                await asyncio.sleep(interval)
                try:
                    await self.manager.renew(self.lease)
                except Exception:
                    self.lost.set()
                    logger.exception("RC-05 lease heartbeat lost")
                    return
        except asyncio.CancelledError:
            raise


class PostgresEvidenceChain:
    """Tenant-scoped, append-only, HMAC-attested evidence chain."""

    def __init__(self, pool: AsyncConnectionPool, secret: bytes) -> None:
        if not secret:
            raise ValueError("evidence signing secret must not be empty")
        self.pool = pool
        self.secret = secret

    @staticmethod
    def _canonical(payload: dict[str, Any]) -> str:
        return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    def _event_hash(self, payload: dict[str, Any], previous_hash: str | None) -> str:
        material = self._canonical({"previous": previous_hash, "payload": payload}).encode()
        return hashlib.sha256(material).hexdigest()

    def _signature(self, tenant_id: str, thread_id: str, event_hash: str) -> str:
        material = f"{tenant_id}:{thread_id}:{event_hash}".encode()
        return hmac.new(self.secret, material, hashlib.sha256).hexdigest()

    async def append(
        self,
        tenant_id: str,
        thread_id: str,
        event_type: str,
        context: dict[str, Any],
    ) -> str:
        payload = {
            "tenant_id": tenant_id,
            "thread_id": thread_id,
            "event_type": event_type,
            "context": context,
            "recorded_at": datetime.now(UTC).isoformat(),
        }
        payload_hash = hashlib.sha256(self._canonical(payload).encode()).hexdigest()
        async with self.pool.connection() as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT event_hash FROM ois_attestation_evidence "
                    "WHERE tenant_id = %s AND thread_id = %s ORDER BY sequence_no DESC LIMIT 1",
                    (tenant_id, thread_id),
                )
                row = await cur.fetchone()
                previous_hash = row[0] if row else None
                event_hash = self._event_hash(payload, previous_hash)
                signature = self._signature(tenant_id, thread_id, event_hash)
                await cur.execute(
                    """
                    INSERT INTO ois_attestation_evidence
                      (tenant_id, thread_id, event_type, payload_hash, context_snapshot,
                       previous_event_hash, event_hash, attestation_signature)
                    VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s, %s)
                    """,
                    (
                        tenant_id,
                        thread_id,
                        event_type,
                        payload_hash,
                        self._canonical(context),
                        previous_hash,
                        event_hash,
                        signature,
                    ),
                )
                await conn.commit()
        return event_hash


DbOperation = Callable[[psycopg.AsyncCursor[Any], int], Awaitable[Any]]


class OISProductionResilience:
    """RC-04/RC-05 infrastructure adapter around the existing OIS Kernel."""

    def __init__(
        self,
        db_pool: AsyncConnectionPool,
        redis_client: redis.Redis,
        evidence_secret: bytes,
        *,
        recovery_pool: AsyncConnectionPool | None = None,
        lease_ttl_ms: int = 10_000,
    ) -> None:
        self.db_pool = db_pool
        self.recovery_pool = recovery_pool
        self.leases = FencedLeaseManager(redis_client, lease_ttl_ms)
        self.evidence = PostgresEvidenceChain(db_pool, evidence_secret)

    @staticmethod
    async def _set_tenant(cur: psycopg.AsyncCursor[Any], tenant_id: str) -> None:
        await cur.execute("SELECT set_config('app.current_tenant_id', %s, true)", (tenant_id,))

    async def _write_dlq(
        self,
        ctx: KernelTaskContext,
        scenario_id: str,
        state_dump: dict[str, Any],
        error_message: str,
    ) -> None:
        if self.recovery_pool is None:
            raise RecoverySinkUnavailable("RC-04 durable recovery_pool is not configured")
        canonical = json.dumps(state_dump, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
        context_hash = hashlib.sha256(canonical.encode()).hexdigest()
        signature = hmac.new(
            self.evidence.secret,
            f"{ctx.tenant_id}:{ctx.thread_id}:{scenario_id}:{context_hash}".encode(),
            hashlib.sha256,
        ).hexdigest()
        async with self.recovery_pool.connection() as conn:
            async with conn.cursor() as cur:
                await self._set_tenant(cur, ctx.tenant_id)
                await cur.execute(
                    """
                    INSERT INTO ois_kernel_dead_letter_queue
                      (tenant_id, thread_id, last_scenario_id, error_diagnostic_log,
                       frozen_context_data, context_hash, cryptographic_seal_signature)
                    VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s)
                    """,
                    (
                        ctx.tenant_id,
                        ctx.thread_id,
                        scenario_id,
                        error_message,
                        canonical,
                        context_hash,
                        signature,
                    ),
                )
                await conn.commit()

    async def execute_fenced_transaction(
        self,
        ctx: KernelTaskContext,
        scenario_id: str,
        db_operation: DbOperation,
        state_dump: dict[str, Any],
    ) -> Any:
        """Run one protected operation with bounded retries and fencing.

        The operation MUST apply the supplied fencing token to its protected
        mutation predicate. Redis ownership checks alone cannot prevent a stale
        worker from racing a downstream commit.
        """
        lock_key = f"ois:lease:{ctx.tenant_id}:{ctx.thread_id}"
        lease = await self.leases.acquire(lock_key)
        started = asyncio.get_running_loop().time()
        retry_count = 0
        try:
            async with LeaseHeartbeat(self.leases, lease) as heartbeat:
                while True:
                    try:
                        await self.leases.assert_current(lease)
                        async with self.db_pool.connection() as conn:
                            async with conn.cursor() as cur:
                                await self._set_tenant(cur, ctx.tenant_id)
                                await self.leases.assert_current(lease)
                                result = await db_operation(cur, lease.fencing_token)
                                if heartbeat.lost.is_set():
                                    raise FencingTokenMismatch("RC-05 heartbeat lost during protected operation")
                                await self.leases.assert_current(lease)
                                await conn.commit()
                        await self.evidence.append(
                            ctx.tenant_id,
                            ctx.thread_id,
                            "TRANSACTION_SUCCESS",
                            {"scenario_id": scenario_id, "fencing_token": lease.fencing_token},
                        )
                        return result
                    except (psycopg.OperationalError, OSError) as exc:
                        retry_count += 1
                        recovery_counter.add(1, {"scenario_id": scenario_id})
                        elapsed = asyncio.get_running_loop().time() - started
                        if retry_count > ctx.max_retries or elapsed >= ctx.retry_deadline_s:
                            await self._write_dlq(ctx, scenario_id, state_dump, str(exc))
                            dlq_counter.add(1, {"scenario_id": scenario_id})
                            await self.evidence.append(
                                ctx.tenant_id,
                                ctx.thread_id,
                                "RECOVERY_DLQ",
                                {"scenario_id": scenario_id, "retry_count": retry_count},
                            )
                            raise RetryExhaustedException(
                                "RC-04 retry/deadline budget exhausted"
                            ) from exc
                        ceiling = min(ctx.max_backoff_s, ctx.base_backoff_s * (2**retry_count))
                        delay = random.uniform(0.0, ceiling)
                        await self.evidence.append(
                            ctx.tenant_id,
                            ctx.thread_id,
                            "RECOVERY_RETRY",
                            {"scenario_id": scenario_id, "retry_count": retry_count, "delay_s": delay},
                        )
                        await asyncio.sleep(delay)
                    except FencingTokenMismatch:
                        lease_collision_counter.add(1, {"scenario_id": scenario_id})
                        await self.evidence.append(
                            ctx.tenant_id,
                            ctx.thread_id,
                            "RC05_FENCING_REJECTED",
                            {"scenario_id": scenario_id, "fencing_token": lease.fencing_token},
                        )
                        raise
        finally:
            try:
                await self.leases.release(lease)
            except Exception:
                logger.exception("RC-05 conditional release failed; never issue unconditional DEL")


RECOVERY_SCENARIO_IDS: tuple[str, ...] = tuple(f"RC-{index:02d}" for index in range(1, 13))


def validate_recovery_matrix(handlers: dict[str, Callable[..., Awaitable[Any]]]) -> None:
    """Fail closed if the canonical 12-scenario suite is incomplete."""
    missing = [scenario_id for scenario_id in RECOVERY_SCENARIO_IDS if scenario_id not in handlers]
    if missing:
        raise KernelPanicException(f"Recovery conformance matrix incomplete: {', '.join(missing)}")
