# Unified Niceone Engineering Workspace Standard

**Status:** Migration proposal — Python 3.15 compatibility must pass CI before production promotion.

## Canonical repositories currently visible to the connected GitHub account

- `niceoneobsidian/niceone-obsidian` — OIS platform and execution kernel.
- `niceoneobsidian/universal-social-intelligence` — standalone social URL/document ingestion capability.
- `niceoneobsidian/niceone-command` — command/project utility; no Python package manifest was found at the audited revision.

The repository name `niceone` and `obsidian-design-intelligence` were not visible to the connected GitHub account during this audit. Do not assume those repositories are migrated until access and their default branches are verified.

## Python policy

- **Developer target:** CPython 3.15.0, the stable release published on 9 October 2026.
- **Compatibility floor:** retain each package's declared `requires-python` contract until support is deliberately dropped. OIS currently declares `>=3.12`; USIE currently declares `>=3.11`.
- **CI migration gate:** retain existing compatibility CI and add a separate Python 3.15 job. Do not remove the existing baseline until 3.15 passes on all required platforms and integrations.
- **Runtime promotion:** Python 3.15 is not considered production-certified merely because the interpreter is stable. Require green unit/integration tests, dependency installation, container build, migrations, and deployment-image verification.
- **No experimental free-threaded build** in production until separately benchmarked and validated.

## Tooling policy

- Use a single, pinned `uv` version for Python interpreter provisioning and environment operations.
- Prefer committed lockfiles for repeatable dependency resolution. OIS already has `uv.lock`; USIE must generate and validate its own lockfile before claiming reproducible dependency parity.
- Standardize Ruff, pytest, pytest-asyncio, and mypy versions through explicit constraints and lockfiles. Do not force the same application dependency set across different projects.
- Keep Ruff's language target and mypy's target aligned with the package's supported compatibility floor, not automatically with the newest developer interpreter.
- Keep secrets out of repository files; use environment-specific secret providers and least-privilege CI permissions.

## Workspace layout

Keep the repositories separate so each retains its own release boundary and dependency graph. Clone them as sibling folders and open them together in a local multi-root VS Code workspace. Share editor settings, task conventions, formatting/lint commands, and version policy; do not combine their runtime dependencies into one virtual environment.

Suggested local layout:

```text
Niceone/
├── niceone-obsidian/
├── universal-social-intelligence/
└── niceone-command/
```

Use one virtual environment per Python repository. Never share `.venv` directories across projects.

## Promotion gates

1. Python 3.15 dependency installation succeeds from a clean environment.
2. Formatting, lint, type checks, and all unit tests pass.
3. Integration tests pass against the project's required services.
4. Docker/production images build and start with the intended interpreter.
5. Lockfiles are reproducible and reviewed.
6. Rollback to the last supported runtime is documented and tested.
7. Only then change the default runtime and deployment images broadly.

## Evidence note

This standard is a migration plan and does not assert that all repositories, packages, CI jobs, or deployment images already support Python 3.15. Record CI links and exact runtime versions in the pull request before promotion.
