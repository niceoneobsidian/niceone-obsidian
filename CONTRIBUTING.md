# Contributing to Niceone Obsidian

## Development contract

Contributions follow: issue or documented intent; dedicated branch; small implementation; tests; pull request review; merge after required checks.

Do not describe architectural intent as implemented capability without evidence.

## Local verification

The supported baseline is Python 3.12+.

```bash
python -m pip install -e ".[test]"
ruff check .
ruff format --check .
python -m mypy ois
python -m pytest -q
```

Integration and recovery tests may require PostgreSQL, Redis, Docker, or other documented infrastructure.

## Pull requests

State what changed, why, tests executed, required infrastructure, security/authorization impact, persistence/idempotency impact, recovery/rollback implications, and evidence limitations.

Security vulnerabilities must not be opened as public issues. Follow SECURITY.md.
