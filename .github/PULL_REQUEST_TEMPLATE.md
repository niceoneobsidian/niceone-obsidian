## Summary

Describe the problem and the change in a few sentences.

## Change type

- [ ] Feature
- [ ] Bug fix
- [ ] Test
- [ ] Documentation
- [ ] Architecture or governance
- [ ] Security
- [ ] Database or migration
- [ ] Operational change

## Verification

List the exact checks run and their results.

```text
# commands and results
```

## Safety and governance

- [ ] Authorization boundaries are preserved.
- [ ] Idempotency and duplicate delivery behavior are considered.
- [ ] State transitions remain valid.
- [ ] Evidence remains append-only and auditable.
- [ ] Secrets and sensitive data are not exposed.
- [ ] Documentation reflects the actual maturity level.

## Operational impact

- Configuration changes:
- Migration required:
- Deployment considerations:
- Monitoring or alerts:
- Rollback or recovery plan:

## Evidence

Link tests, traces, dashboards, issues, design records, or other evidence supporting the change.

## Checklist

- [ ] I read `CONTRIBUTING.md`.
- [ ] I added or updated tests where behavior changed.
- [ ] I ran `git diff --check`.
- [ ] I updated the changelog when appropriate.
- [ ] I have not claimed production readiness without the required evidence.
