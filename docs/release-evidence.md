# Release evidence

A release is a Git tag matching `vMAJOR.MINOR.PATCH`.

The release workflow produces and publishes:

- Source distribution (`sdist`)
- Python wheel
- CycloneDX JSON SBOM
- GitHub artifact attestations for files under `dist/`
- GitHub-generated release notes

## Release checklist

Before creating a release tag:

1. Confirm the target commit passed the required CI checks.
2. Update `CHANGELOG.md`.
3. Confirm `requirements.lock` is current.
4. Review the dependency audit and license scan.
5. Confirm database migrations are backward-compatible or document the migration order.
6. Confirm rollback instructions are current.
7. Create and push a signed or protected `vMAJOR.MINOR.PATCH` tag.

## Verification

```bash
python -m pip install dist/*.whl
python -m pip check
```

On GitHub, verify that the release contains the wheel, source distribution, and SBOM. Verify the artifact attestation before promoting a build to an external environment.

This workflow publishes artifacts only. Deployment and production activation remain separate controlled actions.
