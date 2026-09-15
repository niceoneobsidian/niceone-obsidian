from __future__ import annotations

import psycopg


def test_migrations_create_tables(
    migrated_postgres: str,
) -> None:
    with psycopg.connect(migrated_postgres) as connection, connection.cursor() as cursor:
        cursor.execute(
            """
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                ORDER BY table_name
                """
        )

        tables = {row[0] for row in cursor.fetchall()}

    assert tables, "Migrations created no public tables"

    print("Migration-created tables:", sorted(tables))


def test_database_is_postgresql(
    migrated_postgres: str,
) -> None:
    with psycopg.connect(migrated_postgres) as connection, connection.cursor() as cursor:
        cursor.execute("SELECT version()")
        version = cursor.fetchone()[0]

    assert "PostgreSQL" in version
