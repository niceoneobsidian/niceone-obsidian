from __future__ import annotations

# ruff: noqa: I001

import re
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS_DIR = PROJECT_ROOT / "migrations"
MIGRATION_NAME = re.compile(r"^\d{3}_[a-z0-9]+(?:_[a-z0-9]+)*\.sql$")


def test_migration_versions_are_unique_and_numeric() -> None:
    migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    versions = [path.name.split("_", 1)[0] for path in migration_files]

    assert versions == sorted(versions, key=int)
    assert len(versions) == len(set(versions))
    assert all(version.isdigit() for version in versions)


def test_migration_versions_are_contiguous() -> None:
    versions = sorted(int(path.name.split("_", 1)[0]) for path in MIGRATIONS_DIR.glob("*.sql"))
    assert versions == list(range(1, len(versions) + 1))


def test_migration_filenames_follow_the_repository_contract() -> None:
    migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))

    assert migration_files, "No SQL migrations found"
    invalid_names = [
        path.name for path in migration_files if not MIGRATION_NAME.fullmatch(path.name)
    ]
    assert not invalid_names, f"Invalid migration filenames: {invalid_names}"


def test_migration_files_are_nonempty_utf8_sql() -> None:
    migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))

    assert migration_files, "No SQL migrations found"
    for path in migration_files:
        contents = path.read_text(encoding="utf-8")
        assert contents.strip(), f"Migration is empty: {path.name}"
