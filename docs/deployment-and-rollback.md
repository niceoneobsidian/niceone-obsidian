# Deployment and Rollback

## Supported deployment path

1. Review target commit and release notes.
2. Run repository verification.
3. Build an immutable artifact from the reviewed commit.
4. Record artifact digest and source commit.
5. Deploy to a non-production environment.
6. Run health, readiness, authorization, persistence, and recovery checks.
7. Promote only after evidence gates pass.
8. Record deployment evidence.

The repository does not currently declare one production hosting provider as the universal runtime. Provider-specific manifests are deployment adapters.

## Rollback

Rollback must use a previously verified immutable artifact. Database migrations require an explicit compatibility and rollback plan; application rollback does not imply schema rollback.

## Required evidence

Record source commit, artifact digest, dependency-lock identifier, migration version, configuration version, verification results, and rollback target.
