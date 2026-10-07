# OIS Production Control Contract

## Deployment

1. Build an immutable artifact from a reviewed commit.
2. Run repository verification and security checks.
3. Apply forward-compatible migrations using the migration runner.
4. Deploy application workers and control-plane components.
5. Verify SLO/SLI health and governance decision rates.
6. Promote only after evidence is recorded.

## Rollback

Application rollback restores a previously verified immutable artifact. It does not imply
database rollback. Schema changes must remain backward compatible until the old artifact is
no longer serving traffic.

## Disaster recovery

Backups must be encrypted, retained according to the operating policy, and periodically
restored into an isolated environment. A restore is not considered verified until integrity,
tenant isolation, durable execution state, and governance audit/provenance records are checked.

## Evidence

A release evidence bundle should contain the release commit, migration versions, test results,
security scan results, backup/restore result, SLO snapshot, and rollback rehearsal result.
