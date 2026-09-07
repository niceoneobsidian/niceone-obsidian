from __future__ import annotations

import asyncio
import logging
import random
from dataclasses import dataclass
from enum import Enum
from typing import Any, Awaitable, Callable, Optional, Protocol, Sequence

logger = logging.getLogger("ois.chaos_interceptor")


class ChaosMode(str, Enum):
    NETWORK_SPLIT = "NETWORK_SPLIT"
    DATABASE_TIMEOUT = "DATABASE_TIMEOUT"


@dataclass(frozen=True)
class ChaosConfig:
    failure_probability: float = 0.15
    timeout_min_seconds: float = 2.5
    timeout_max_seconds: float = 6.0
    enabled: bool = False
    modes: Sequence[ChaosMode] = (ChaosMode.NETWORK_SPLIT, ChaosMode.DATABASE_TIMEOUT)

    def __post_init__(self) -> None:
        if not 0 <= self.failure_probability <= 1:
            raise ValueError("failure_probability must be between 0 and 1")
        if self.timeout_min_seconds < 0 or self.timeout_max_seconds < self.timeout_min_seconds:
            raise ValueError("invalid chaos timeout bounds")
        if not self.modes:
            raise ValueError("at least one chaos mode is required")


class AsyncPool(Protocol):
    def connection(self) -> Any: ...


class ChaosInjectionEngine:
    """Fail-closed, deterministic-testable DB fault interceptor; disabled by default."""

    def __init__(self, config: Optional[ChaosConfig] = None,
                 rng: Optional[random.Random] = None) -> None:
        self.config = config or ChaosConfig()
        self.rng = rng or random.Random()
        self._enabled = self.config.enabled

    @property
    def enabled(self) -> bool:
        return self._enabled

    def activate_chaos_matrix(self) -> None:
        self._enabled = True
        logger.warning("CHAOS_INJECTION_ENABLED")

    def deactivate_chaos_matrix(self) -> None:
        self._enabled = False
        logger.info("CHAOS_INJECTION_DISABLED")

    def choose_fault(self) -> Optional[ChaosMode]:
        if not self._enabled or self.rng.random() >= self.config.failure_probability:
            return None
        return self.rng.choice(list(self.config.modes))

    async def execute_intercepted_db_call(
        self,
        pool: AsyncPool,
        tenant_id: str,
        query: str,
        params: tuple[Any, ...] = (),
        *,
        set_tenant: Callable[[Any, str], Awaitable[None]],
    ) -> Any:
        fault = self.choose_fault()
        if fault is ChaosMode.NETWORK_SPLIT:
            raise ConnectionResetError("simulated database connection reset")

        async with pool.connection() as conn:
            if fault is ChaosMode.DATABASE_TIMEOUT:
                delay = self.rng.uniform(self.config.timeout_min_seconds,
                                         self.config.timeout_max_seconds)
                logger.warning("CHAOS_DATABASE_TIMEOUT delay=%.2f", delay)
                await asyncio.sleep(delay)

            await set_tenant(conn, tenant_id)
            async with conn.cursor() as cur:
                await cur.execute(query, params)
                if cur.description:
                    return await cur.fetchall()
                await conn.commit()
                return None


async def parameterized_tenant_context(conn: Any, tenant_id: str) -> None:
    """Set RLS context without interpolating tenant identifiers into SQL."""
    async with conn.cursor() as cur:
        await cur.execute(
            "SELECT set_config('app.current_tenant_id', %s, true)",
            (tenant_id,),
        )
