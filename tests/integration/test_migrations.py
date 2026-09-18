from __future__ import annotations

from pathlib import Path

import psycopg
import pytest

from tests.helpers.migrations import apply_migrations

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS_DIR = PROJECT_ROOT / "migrations"


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
    assert "schema_migrations" in tables


def test_database_is_postgresql(
    migrated_postgres: str,
) -> None:
    with psycopg.connect(migrated_postgres) as connection, connection.cursor() as cursor:
        cursor.execute("SELECT version()")
        version = cursor.fetchone()[0]

    assert "PostgreSQL" in version


def test_schema_migrations_records_all_migrations(
    migrated_postgres: str,
) -> None:
    """Verify that every applied migration is recorded with a valid SHA256 checksum."""
    with psycopg.connect(migrated_postgres) as connection, connection.cursor() as cursor:
        cursor.execute(
            "SELECT version, name, checksum, applied_at FROM schema_migrations ORDER BY version"
        )
        rows = cursor.fetchall()

    recorded_versions = [row[0] for row in rows]
    expected_versions = ["001", "002", "003", "004", "005"]
    assert recorded_versions == expected_versions

    for row in rows:
        version, name, checksum, applied_at = row
        assert len(checksum) == 64  # Valid SHA-256 hex string
        assert name.startswith(version)
        assert applied_at is not None


def test_migration_runner_detects_checksum_tampering(
    migrated_postgres: str,
    tmp_path: Path,
) -> None:
    """Verify that tampering with an applied migration fails closed."""
    fake_migrations = tmp_path / "migrations"
    fake_migrations.mkdir()

    for migration_file in MIGRATIONS_DIR.glob("*.sql"):
        destination = fake_migrations / migration_file.name
        destination.write_text(
            migration_file.read_text(encoding="utf-8"),
            encoding="utf-8",
        )

    tampered_file = fake_migrations / "001_durable_execution.sql"
    tampered_file.write_text(
        tampered_file.read_text(encoding="utf-8") + "\n-- tampered content\n",
        encoding="utf-8",
    )

    with (
        psycopg.connect(migrated_postgres) as connection,
        pytest.raises(RuntimeError, match="checksum mismatch"),
    ):
        apply_migrations(connection, fake_migrations)
