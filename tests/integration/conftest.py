from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import psycopg
import pytest
from testcontainers.community.postgres import PostgresContainer

from tests.helpers.migrations import apply_migrations

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS_DIR = PROJECT_ROOT / "migrations"


@pytest.fixture(scope="session")
def postgres_container() -> Iterator[PostgresContainer]:
    """
    Start one isolated PostgreSQL instance for the integration test session.

    The port is dynamically mapped by Testcontainers.
    """
    with PostgresContainer(
        image="postgres:16-alpine",
        username="test_user",
        password="test_password",
        dbname="test_database",
    ) as container:
        yield container


@pytest.fixture(scope="session")
def postgres_dsn(
    postgres_container: PostgresContainer,
) -> str:
    """
    Return the dynamically mapped connection string.
    """
    return (
        postgres_container.get_connection_url()
        .replace("postgresql+psycopg2://", "postgresql://")
        .replace("postgresql+psycopg://", "postgresql://")
    )


@pytest.fixture(scope="session")
def migrated_postgres(
    postgres_dsn: str,
) -> str:
    """
    Apply all real repository migrations before any integration test runs.
    """
    with psycopg.connect(postgres_dsn, autocommit=False) as connection:
        apply_migrations(connection, MIGRATIONS_DIR)

    return postgres_dsn


@pytest.fixture
def postgres_connection(
    migrated_postgres: str,
) -> Iterator[psycopg.Connection]:
    connection = psycopg.connect(migrated_postgres)

    try:
        yield connection
    finally:
        connection.rollback()
        connection.close()
