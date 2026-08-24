"""Environment-backed Social Growth production configuration."""
from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class SocialProductionConfig:
    postgres_dsn: str | None
    x_token: str | None
    linkedin_token: str | None
    linkedin_version: str
    meta_token: str | None
    meta_graph_version: str

    @classmethod
    def from_env(cls) -> "SocialProductionConfig":
        return cls(
            postgres_dsn=os.getenv("OIS_POSTGRES_DSN"),
            x_token=os.getenv("OIS_X_BEARER_TOKEN"),
            linkedin_token=os.getenv("OIS_LINKEDIN_ACCESS_TOKEN"),
            linkedin_version=os.getenv("OIS_LINKEDIN_VERSION", "202604"),
            meta_token=os.getenv("OIS_META_ACCESS_TOKEN"),
            meta_graph_version=os.getenv("OIS_META_GRAPH_VERSION", "v23.0"),
        )

    def validate(self, *, require_database: bool = True) -> list[str]:
        errors: list[str] = []
        if require_database and not self.postgres_dsn:
            errors.append("OIS_POSTGRES_DSN is required for production persistence")
        return errors
