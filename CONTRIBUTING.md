# Contributing to Niceone Obsidian

Thank you for contributing to the Obsidian Intelligence System. The project is under controlled implementation, so changes should preserve explicit authorization, validation, evidence, recovery, and rollback boundaries.

## Before you start

1. Read the [README](README.md) and relevant material in [`docs/`](docs/).
2. Search existing issues and pull requests before opening new work.
3. For security vulnerabilities, follow [SECURITY.md](SECURITY.md) instead of opening a public issue.
4. For a material architectural change, open an architecture-proposal issue first.

## Development setup

Use Python 3.12 or newer. A typical local setup is:

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[test]"
```

Copy `.env.example` to `.env` and provide only local development values. Never commit `.env`.

## Checks before opening a pull request

Run the checks relevant to your change:

```bash
ruff check .
ruff format --check .
mypy .
bandit -r ois
pytest
```

For persistence or migration changes, also run the integration tests with Docker available. For recovery changes, run the recovery conformance suite.

## Change design rules

- Treat model output as untrusted input and a proposal.
- Require explicit authorization before consequential actions.
- Preserve idempotency across retries and duplicate delivery.
- Keep evidence append-only and auditable.
- Enforce valid state transitions at the persistence boundary where possible.
- Add or update tests with every behavior change.
- Document operational impact, rollback, and migration requirements.
- Avoid unrelated formatting or refactoring in focused changes.

## Commit and pull-request guidance

Use focused commits and descriptive imperative messages, for example:

```text
feat: enforce durable execution idempotency
fix: reject invalid persisted state transition
docs: document recovery invariants
test: cover duplicate delivery
```

Pull requests should explain the problem, the design, the verification performed, operational impact, and rollback plan. Keep the draft open while the design is still changing.

## Review expectations

At least one maintainer review is expected for normal changes. Changes involving authorization, execution, persistence, migrations, recovery, security, or CI supply chain should receive focused review from an owner of the affected area.

## Documentation changes

Update documentation when behavior, configuration, operational procedures, public interfaces, or maturity claims change. Do not describe a capability as production verified unless implementation, testing, integration, runtime, deployment, and rollback evidence exists.

## Contributor license agreement

This repository does not currently require a separate contributor license agreement. By submitting a contribution, you agree that it may be distributed under the repository's Apache-2.0 license.
