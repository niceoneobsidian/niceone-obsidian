from __future__ import annotations

from pathlib import Path

import psycopg


def apply_migrations(
    connection: psycopg.Connection,
    migrations_dir: Path,
) -> None:
    migration_files = sorted(migrations_dir.glob("*.sql"))

    if not migration_files:
        raise RuntimeError(
            f"No SQL migration files found in {migrations_dir}"
        )

    with connection.transaction():
        with connection.cursor() as cursor:
            for migration_file in migration_files:
                sql = migration_file.read_text(
                    encoding="utf-8"
                ).strip()

                if not sql:
                    raise RuntimeError(
                        f"Migration file is empty: {migration_file}"
                    )

                print(f"Applying migration: {migration_file.name}")
                cursor.execute(sql)
