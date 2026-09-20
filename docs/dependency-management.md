# Dependency management

## Supported environment

- Python 3.12 or newer
- PostgreSQL for integration tests
- Redis for integration tests and runtime components that require it

## Lock policy

`requirements.lock` is the CI installation contract. It pins the direct runtime and test roots used by this repository so that CI and local verification do not silently resolve a different application stack.

The lock is intentionally reviewed like source code. Dependency upgrades must:

1. Update `pyproject.toml` constraints when the supported range changes.
2. Update `requirements.lock` in the same change.
3. Run the full quality and integration checks.
4. Review the generated license and SBOM artifacts.
5. Record security-relevant upgrades in `CHANGELOG.md`.

The lock file currently pins direct roots. Transitive dependency resolution remains delegated to pip's resolver. Before production packaging, generate a hash-complete transitive lock with the project's selected packaging tool and commit it alongside this file.

## Local verification

```bash
python -m pip install --upgrade pip
python -m pip install --requirement requirements.lock
python -m pip check
python -m pytest -q
```

For editable development with the repository's optional test dependencies:

```bash
python -m pip install -e ".[test]"
```

## Automated checks

- `.github/workflows/dependency-lock.yml` installs the lock and runs `pip check`.
- `.github/workflows/supply-chain.yml` builds a CycloneDX SBOM and runs dependency auditing.
- Dependabot raises weekly dependency and GitHub Actions update pull requests.

Do not commit credentials, private package indexes, or generated virtual environments.
