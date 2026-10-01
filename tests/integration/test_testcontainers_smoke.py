from __future__ import annotations

import psycopg
from testcontainers.community.postgres import PostgresContainer


def test_testcontainers_can_start_postgres() -> None:
    with PostgresContainer(
        image="postgres:16-alpine",
        username="test_user",
        password="test_password",
        dbname="test_database",
    ) as container:
        dsn = container.get_connection_url()

        dsn = dsn.replace("postgresql+psycopg2://", "postgresql://").replace(
            "postgresql+psycopg://", "postgresql://"
        )

        with psycopg.connect(dsn) as connection, connection.cursor() as cursor:
            cursor.execute("SELECT version()")
            version = cursor.fetchone()[0]  # type: ignore

        assert version is not None
        assert "PostgreSQL" in version
