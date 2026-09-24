from __future__ import annotations

# ruff: noqa: I001

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
MIGRATIONS_DIR = PROJECT_ROOT / "migrations"


def test_migration_versions_are_unique_and_numeric() -> None:
    migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
    versions = [path.name.split("_", 1)[0] for path in migration_files]

    assert versions == sorted(versions, key=int)
    assert len(versions) == len(set(versions))
    assert all(version.isdigit() for version in versions)


def test_migration_versions_are_contiguous() -> None:
    versions = sorted(
        int(path.name.split("_", 1)[0])
        for path in MIGRATIONS_DIR.glob("*.sql")
    )
    assert versions == list(range(1, len(versions) + 1))
