from __future__ import annotations

import shutil
from pathlib import Path

import psycopg
import pytest

from ois.database.migrations import apply_migrations

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPOSITORY_MIGRATIONS = PROJECT_ROOT / "migrations"


def _copy_repository_migrations(destination: Path) -> Path:
    destination.mkdir()
    for migration in REPOSITORY_MIGRATIONS.glob("*.sql"):
        shutil.copyfile(migration, destination / migration.name)
    return destination


def test_production_runner_orders_migrations_numerically(
    migrated_postgres: str,
    tmp_path: Path,
) -> None:
    migrations_dir = _copy_repository_migrations(tmp_path / "migrations")
    (migrations_dir / "9002_create_numeric_order_probe.sql").write_text(
        "CREATE TABLE migration_numeric_order_probe (value integer NOT NULL);",
        encoding="utf-8",
    )
    # Lexical sorting would place 90010 before 9002; numeric sorting must not.
    (migrations_dir / "90010_insert_numeric_order_probe.sql").write_text(
        "INSERT INTO migration_numeric_order_probe (value) VALUES (10);",
        encoding="utf-8",
    )

    with psycopg.connect(migrated_postgres) as connection:
        apply_migrations(connection, migrations_dir)

    with psycopg.connect(migrated_postgres) as connection, connection.cursor() as cursor:
        cursor.execute("SELECT value FROM migration_numeric_order_probe")
        assert cursor.fetchall() == [(10,)]


def test_production_runner_rejects_duplicate_numeric_versions(
    migrated_postgres: str,
    tmp_path: Path,
) -> None:
    migrations_dir = tmp_path / "migrations"
    migrations_dir.mkdir()
    (migrations_dir / "9002_first.sql").write_text("SELECT 1;", encoding="utf-8")
    (migrations_dir / "09002_duplicate.sql").write_text("SELECT 2;", encoding="utf-8")

    with psycopg.connect(migrated_postgres) as connection:
        with pytest.raises(RuntimeError, match="Duplicate migration version"):
            apply_migrations(connection, migrations_dir)


def test_production_runner_rejects_empty_migrations(
    migrated_postgres: str,
    tmp_path: Path,
) -> None:
    migrations_dir = _copy_repository_migrations(tmp_path / "migrations")
    (migrations_dir / "90020_empty.sql").write_text("  \n", encoding="utf-8")

    with psycopg.connect(migrated_postgres) as connection:
        with pytest.raises(RuntimeError, match="Migration is empty"):
            apply_migrations(connection, migrations_dir)


def test_production_runner_detects_checksum_tampering(
    migrated_postgres: str,
    tmp_path: Path,
) -> None:
    migrations_dir = _copy_repository_migrations(tmp_path / "migrations")
    tampered = migrations_dir / "001_durable_execution.sql"
    tampered.write_text(
        tampered.read_text(encoding="utf-8") + "\n-- tampered content\n",
        encoding="utf-8",
    )

    with psycopg.connect(migrated_postgres) as connection:
        with pytest.raises(RuntimeError, match="checksum mismatch"):
            apply_migrations(connection, migrations_dir)


def test_production_runner_is_idempotent(
    migrated_postgres: str,
    tmp_path: Path,
) -> None:
    migrations_dir = _copy_repository_migrations(tmp_path / "migrations")
    (migrations_dir / "90020_create_repeat_probe.sql").write_text(
        "CREATE TABLE migration_repeat_probe (value integer NOT NULL);"
        "INSERT INTO migration_repeat_probe (value) VALUES (1);",
        encoding="utf-8",
    )

    with psycopg.connect(migrated_postgres) as connection:
        apply_migrations(connection, migrations_dir)
    with psycopg.connect(migrated_postgres) as connection:
        apply_migrations(connection, migrations_dir)

    with psycopg.connect(migrated_postgres) as connection, connection.cursor() as cursor:
        cursor.execute("SELECT value FROM migration_repeat_probe")
        assert cursor.fetchall() == [(1,)]
        cursor.execute("SELECT count(*) FROM schema_migrations WHERE version = '90020'")
        assert cursor.fetchone() == (1,)


def test_production_runner_rolls_back_all_pending_migrations_on_failure(
    migrated_postgres: str,
    tmp_path: Path,
) -> None:
    migrations_dir = _copy_repository_migrations(tmp_path / "migrations")
    (migrations_dir / "90030_create_rollback_probe.sql").write_text(
        "CREATE TABLE migration_rollback_probe (value integer NOT NULL);",
        encoding="utf-8",
    )
    (migrations_dir / "90031_force_rollback.sql").write_text(
        "SELECT * FROM ois_table_that_does_not_exist;",
        encoding="utf-8",
    )

    with psycopg.connect(migrated_postgres) as connection:
        with pytest.raises(psycopg.Error):
            apply_migrations(connection, migrations_dir)

    with psycopg.connect(migrated_postgres) as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT count(*) FROM information_schema.tables
            WHERE table_schema = 'public' AND table_name = 'migration_rollback_probe'
            """
        )
        assert cursor.fetchone() == (0,)
        cursor.execute("SELECT count(*) FROM schema_migrations WHERE version = '90030'")
        assert cursor.fetchone() == (0,)
