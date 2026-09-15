from __future__ import annotations

from pathlib import Path

import psycopg


def apply_migrations(
    connection: psycopg.Connection,
    migrations_dir: Path,
) -> None:
    """
    Apply all SQL migrations in lexical filename order.

    This intentionally runs the same SQL files used by the application.
    It is not a mock and does not use a separate test schema definition.
    """
    migration_files = sorted(migrations_dir.glob("*.sql"))

    if not migration_files:
        raise RuntimeError(f"No migration files found in {migrations_dir}")

    with connection.transaction():
        with connection.cursor() as cursor:
            for migration_file in migration_files:
                sql = migration_file.read_text(encoding="utf-8")

                if not sql.strip():
                    raise RuntimeError(
                        f"Migration is empty: {migration_file.name}"
                    )

                cursor.execute(sql)
