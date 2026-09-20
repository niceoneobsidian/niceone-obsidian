# Developer quickstart

This guide gets a contributor from a clean checkout to the fast local verification loop. The repository is under controlled implementation; the commands below verify development behavior, not production readiness.

## Prerequisites

- Python 3.12 or newer.
- Docker Desktop or another Docker-compatible runtime for integration tests.
- Git.
- PostgreSQL and Redis are supplied by the integration-test setup or local infrastructure.

## Create an environment

```bash
git clone https://github.com/niceoneobsidian/niceone-obsidian.git
cd niceone-obsidian
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[test]"
cp .env.example .env
```

Review `.env` before running anything. Use local-only credentials and never commit the file.

## Fast checks

```bash
ruff check .
ruff format --check .
mypy .
bandit -r ois
pytest -m 'not integration'
```

## Integration checks

With Docker running, execute:

```bash
pytest -m integration
```

Integration tests may create disposable PostgreSQL and Redis resources. Do not point them at a shared or production database.

## Focused checks

```bash
pytest tests/conformance -q
pytest tests/integration -q
pytest tests/social_growth -q
```

Use the path that matches your change. If a test path differs on your branch, prefer the repository's current test layout.

## Development loop

1. Start from a dedicated branch.
2. Read the relevant architecture and governance documentation.
3. Make the smallest coherent change.
4. Add tests and evidence for changed behavior.
5. Run focused checks, then the full fast suite.
6. Update operational or maturity documentation when claims change.
7. Open a pull request using the repository template.

## Common safety checks

Before pushing:

```bash
git status --short
git diff --check
git grep -n -E '(^|[= ])(sk-|ghp_|AKIA|BEGIN .* PRIVATE KEY)' -- ':!*.lock' || true
```

The grep command is a heuristic, not a replacement for secret scanning.
