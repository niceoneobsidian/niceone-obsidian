# Dependency management

## Supported environment

- Python 3.12 or newer
- PostgreSQL for integration tests
- Redis for integration tests and runtime components that require it

## Lock policy

`uv.lock` is the source of truth for dependency resolution. It records the full transitive graph, exact versions and hashes for Python 3.12.

`requirements.lock` is **generated from `uv.lock`** (hashed, direct plus transitive, runtime plus the `test` extra) and is the installation contract for pip-based CI jobs (`supply-chain.yml`, `release.yml`, and the install check in `dependency-lock.yml`). Do not edit it by hand.

The locks are reviewed like source code. Dependency upgrades must:

1. Update `pyproject.toml` constraints when the supported range changes.
2. Regenerate both lock files in the same change (see below).
3. Run the full quality and integration checks.
4. Review the generated license and SBOM artifacts.
5. Record security-relevant upgrades in `CHANGELOG.md`.

## Refreshing the locks

Run **Actions -> Dependency Lock -> Run workflow** on a feature branch (never the default branch) with `write_lock = true`. The workflow pins uv, regenerates `uv.lock`, exports `requirements.lock`, verifies a hash-checked install, and commits both files to the branch. It refuses to run on the default branch.

Commits pushed with `GITHUB_TOKEN` do not trigger other workflows. Re-run the checks or push a follow-up commit on that branch so the pull request gets fresh CI.

To refresh locally with the pinned tool version (`UV_VERSION` in the workflow):

```bash
uv lock
uv export --frozen --format requirements-txt --hashes --no-emit-project --extra test -o requirements.lock
```

## Local verification

```bash
python -m pip install --upgrade pip
python -m pip install --require-hashes --requirement requirements.lock
python -m pip check
python -m pytest -q
```

For editable development with the repository's optional test dependencies:

```bash
python -m pip install -e ".[test]"
```

## Automated checks

- `.github/workflows/dependency-lock.yml` fails when `uv.lock` is stale relative to `pyproject.toml`, when `requirements.lock` differs from the `uv export` of `uv.lock`, or when the hash-checked install or `pip check` fails.
- `.github/workflows/supply-chain.yml` builds a CycloneDX SBOM and runs dependency auditing.
- Dependabot raises weekly dependency and GitHub Actions update pull requests.

Do not commit credentials, private package indexes, or generated virtual environments.
