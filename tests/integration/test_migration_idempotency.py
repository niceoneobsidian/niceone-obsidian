from __future__ import annotations

from pathlib import Path

import psycopg

from .migrations import apply_migrations

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS_DIR = PROJECT_ROOT / "migrations"


def test_migrations_can_be_applied_twice(
    migrated_postgres: str,
) -> None:
    """
    Verify that applying the repository migrations a second time succeeds.

    The migrated_postgres fixture has already applied the migrations once
    to a clean PostgreSQL Testcontainers database.
    """
    with psycopg.connect(migrated_postgres) as connection:
        apply_migrations(connection, MIGRATIONS_DIR)
