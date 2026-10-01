# Quickstart

## Prerequisites

- Python 3.12 or newer
- Git
- Docker Desktop for integration tests
- PostgreSQL and Redis when required by integration tests

## Install

```bash
git clone https://github.com/niceoneobsidian/niceone-obsidian.git
cd niceone-obsidian
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[test]"
```

## Verify

```bash
ruff check .
ruff format --check .
python -m mypy ois
python -m pytest -q
```

## Execution path

Intent -> Control Plane -> policy/authorization -> capability resolution -> execution contract -> Kernel/Execution Runtime -> persistence -> validation -> evidence.

For durable execution, see docs/durable-execution-postgres.md.

This repository is still a development/pre-production project. Passing local tests is not production deployment evidence.
