"""Transactional PostgreSQL schema migration runner for OIS deployments."""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from collections.abc import Sequence

import psycopg

_MIGRATION_FILENAME = re.compile(r"^(?P<version>[0-9]+)_(?P<name>.+)\.sql$")
# A transaction-scoped lock serializes concurrent migration jobs for this application.
_MIGRATION_LOCK_KEYS = (1330463827, 1296647249)


@dataclass(frozen=True, slots=True)
class Migration:
    """A validated migration file loaded once before opening the transaction."""

    version: int
    version_text: str
    name: str
    sql: str
    checksum: str


def _load_migrations(migrations_dir: Path) -> list[Migration]:
    if not migrations_dir.is_dir():
        raise RuntimeError(f"Migration directory does not exist: {migrations_dir}")

    paths = list(migrations_dir.glob("*.sql"))
    if not paths:
        raise RuntimeError(f"No migration files found in {migrations_dir}")

    migrations: list[Migration] = []
    seen_versions: set[int] = set()

    for path in paths:
        match = _MIGRATION_FILENAME.fullmatch(path.name)
        if match is None:
            raise RuntimeError(
                f"Migration filename must use '<numeric-version>_<name>.sql': {path.name}"
            )

        version_text = match.group("version")
        version = int(version_text)
        if version in seen_versions:
            raise RuntimeError(f"Duplicate migration version detected: {version}")
        seen_versions.add(version)

        raw_sql = path.read_bytes()
        if not raw_sql.strip():
            raise RuntimeError(f"Migration is empty: {path.name}")
        try:
            sql = raw_sql.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise RuntimeError(f"Migration is not valid UTF-8: {path.name}") from exc

        migrations.append(
            Migration(
                version=version,
                version_text=version_text,
                name=path.name,
                sql=sql,
                checksum=hashlib.sha256(raw_sql).hexdigest(),
            )
        )

    return sorted(migrations, key=lambda migration: migration.version)


def apply_migrations(connection: psycopg.Connection, migrations_dir: Path) -> None:
    """Apply numbered SQL migrations atomically with checksum and concurrency guards.

    All pending migrations in one invocation share a transaction. A failure rolls back
    both schema changes and history records from that invocation.
    """
    migrations = _load_migrations(migrations_dir)

    with connection.transaction(), connection.cursor() as cursor:
        cursor.execute(
            "SELECT pg_advisory_xact_lock(%s, %s)",
            _MIGRATION_LOCK_KEYS,
        )
        # Bootstrap is required so migrations 001-004 can be tracked; migration 005
        # creates the same table and adds its applied_at index.
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
        cursor.execute("SELECT version, checksum FROM schema_migrations")
        applied: dict[int, tuple[str, str]] = {}
        for stored_version, stored_checksum in cursor.fetchall():
            try:
                numeric_version = int(stored_version)
            except (TypeError, ValueError) as exc:
                raise RuntimeError(
                    f"Invalid migration version stored in schema_migrations: {stored_version!r}"
                ) from exc
            if numeric_version in applied:
                raise RuntimeError(
                    f"Duplicate applied migration version detected: {numeric_version}"
                )
            applied[numeric_version] = (stored_version, stored_checksum)

        for migration in migrations:
            prior = applied.get(migration.version)
            if prior is not None:
                if migration.checksum != prior[1]:
                    raise RuntimeError(
                        f"Migration checksum mismatch for {migration.name}: "
                        f"database has {prior[1]}, file has {migration.checksum}"
                    )
                continue

            print(f"Applying migration: {migration.name}")
            cursor.execute(migration.sql)
            cursor.execute(
                """
                INSERT INTO schema_migrations (version, name, checksum)
                VALUES (%s, %s, %s)
                """,
                (migration.version_text, migration.name, migration.checksum),
            )


def _default_migrations_dir() -> Path:
    configured = os.environ.get("OIS_MIGRATIONS_DIR")
    if configured:
        return Path(configured)
    working_directory_migrations = Path.cwd() / "migrations"
    if working_directory_migrations.is_dir():
        return working_directory_migrations
    return Path(__file__).resolve().parents[2] / "migrations"


def _connection_parameters() -> dict[str, str | int]:
    required = ("DB_HOST", "DB_NAME", "DB_USER", "DB_PASSWORD")
    missing = [name for name in required if not os.environ.get(name)]
    if missing:
        raise RuntimeError(
            "Missing required database environment variables: " + ", ".join(missing)
        )

    try:
        port = int(os.environ.get("DB_PORT", "5432"))
    except ValueError as exc:
        raise RuntimeError("DB_PORT must be an integer") from exc
    if not 1 <= port <= 65535:
        raise RuntimeError("DB_PORT must be between 1 and 65535")

    parameters: dict[str, str | int] = {
        "host": os.environ["DB_HOST"],
        "port": port,
        "dbname": os.environ["DB_NAME"],
        "user": os.environ["DB_USER"],
        "password": os.environ["DB_PASSWORD"],
    }
    sslmode = os.environ.get("DB_SSLMODE")
    if sslmode:
        parameters["sslmode"] = sslmode
    return parameters


def main(argv: Sequence[str] | None = None) -> int:
    """CLI entry point used by the Kubernetes schema-migration Job."""
    parser = argparse.ArgumentParser(description="Apply OIS PostgreSQL schema migrations.")
    parser.add_argument(
        "--migrations-dir",
        type=Path,
        default=None,
        help="Directory containing numbered SQL migrations (default: migrations/).",
    )
    args = parser.parse_args(argv)
    migrations_dir = args.migrations_dir or _default_migrations_dir()

    try:
        with psycopg.connect(**_connection_parameters()) as connection:
            apply_migrations(connection, migrations_dir)
    except (OSError, ValueError, RuntimeError, psycopg.Error) as exc:
        print(f"ois-migrate failed: {exc}", file=sys.stderr)
        return 1

    print("OIS database migrations completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
