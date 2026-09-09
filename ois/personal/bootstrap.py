"""Production bootstrap for the personal OIS runtime."""

from __future__ import annotations

import os

from ois.kernel.postgres import PostgresDurableExecutionStore

from .platform import PersonalPlatform, PlatformConfig


def build_personal_platform(config: PlatformConfig | None = None) -> PersonalPlatform:
    config = config or PlatformConfig()
    dsn = config.postgres_dsn or os.getenv("OIS_POSTGRES_DSN")
    if not dsn:
        raise RuntimeError("OIS_POSTGRES_DSN is required for the personal durable runtime")
    store = PostgresDurableExecutionStore(dsn)
    platform = PersonalPlatform(config=config, durable_store=store)
    platform.initialize()
    return platform
