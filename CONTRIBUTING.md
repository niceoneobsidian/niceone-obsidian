# Contributing to Niceone Obsidian

## Development contract

Contributions follow: issue or documented intent; dedicated branch; small implementation; tests; pull request review; merge after required checks.

Do not describe architectural intent as implemented capability without evidence.

## Local verification

The supported baseline is Python 3.12+. Run checks from the OIS repository root, using its `.venv`:

```bash
.venv/bin/python -m ruff check .
.venv/bin/python -m ruff format --check .
.venv/bin/python -m mypy ois
env \
	OIS_POSTGRES_TEST_DSN= OIS_TEST_DATABASE_URL= OIS_TEST_REDIS_URL= \
	OIS_POSTGRES_DSN= OIS_LIVE_DATABASE_URL= OIS_DATABASE_URL= OIS_REDIS_URL= \
	.venv/bin/python -m pytest \
	--ignore=tests/integration \
	--ignore=tests/integrations \
	-m 'not integration and not live and not sandbox'
```

The offline pytest command is also available as **OIS: pytest (offline subset)** in VS Code. Do not use an unrestricted `pytest -q` as the default: integration tests can start PostgreSQL through Testcontainers and other integration/live/sandbox tests require separate prerequisites and review. Run those only when their infrastructure and external-operation scope are explicitly approved.

To recreate the OIS environment, run from this repository root:

```bash
python3.12 -m venv .venv
.venv/bin/python -m pip install -e ".[test]"
```

The repository also contains `uv.lock`; the supported setup command above currently uses pip and does not enforce that lock file.

## Pull requests

State what changed, why, tests executed, required infrastructure, security/authorization impact, persistence/idempotency impact, recovery/rollback implications, and evidence limitations.

Security vulnerabilities must not be opened as public issues. Follow SECURITY.md.
