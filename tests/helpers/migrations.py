from __future__ import annotations

import hashlib
from pathlib import Path

import psycopg


def calculate_checksum(file_path: Path) -> str:
    """Calculate SHA-256 checksum of a migration file's contents."""
    return hashlib.sha256(file_path.read_bytes()).hexdigest()


def _migration_version(path: Path) -> int:
    """Return the numeric migration version for deterministic ordering."""
    prefix = path.name.split("_", 1)[0]
    try:
        return int(prefix)
    except ValueError as exc:
        raise RuntimeError(
            f"Migration filename must start with a numeric version: {path.name}"
        ) from exc


def apply_migrations(
    connection: psycopg.Connection,
    migrations_dir: Path,
) -> None:
    """Apply migrations in numeric order with history and checksum tracking."""
    migration_files = sorted(
        migrations_dir.glob("*.sql"),
        key=_migration_version,
    )

    if not migration_files:
        raise RuntimeError(f"No migration files found in {migrations_dir}")

    versions = [_migration_version(path) for path in migration_files]
    if len(versions) != len(set(versions)):
        raise RuntimeError("Duplicate migration version detected")

    with connection.transaction(), connection.cursor() as cursor:
        cursor.execute(
            """
            CREATE TABLE IF NOT EXISTS schema_migrations (
                version TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                checksum TEXT NOT NULL,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
            """
        )

        cursor.execute("SELECT version, checksum FROM schema_migrations ORDER BY version")
        applied_migrations = {row[0]: row[1] for row in cursor.fetchall()}

        for migration_file in migration_files:
            version = migration_file.name.split("_", 1)[0]
            checksum = calculate_checksum(migration_file)
            sql = migration_file.read_text(encoding="utf-8")

            if not sql.strip():
                raise RuntimeError(f"Migration is empty: {migration_file.name}")

            if version in applied_migrations:
                expected_checksum = applied_migrations[version]
                if checksum != expected_checksum:
                    raise RuntimeError(
                        f"Migration checksum mismatch for {migration_file.name}: "
                        f"database has {expected_checksum}, file has {checksum}"
                    )
                continue

            print(f"Applying migration: {migration_file.name}")
            cursor.execute(sql)
            cursor.execute(
                """
                INSERT INTO schema_migrations (version, name, checksum)
                VALUES (%s, %s, %s)
                """,
                (version, migration_file.name, checksum),
            )
