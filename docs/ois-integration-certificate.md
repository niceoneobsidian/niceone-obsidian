# OIS Integration Certificate

The provider certificate is the executable inventory for the OIS v2 Hybrid integration boundary.

## Status model

- VERIFIED: concrete repository implementation and evidence references exist.
- DISABLED_GATED: provider is declared but cannot activate because the canonical environment keeps it disabled and the integration boundary rejects unregistered providers.
- INTERNAL_GATED: OIS has an internal integration surface, but no concrete external provider is selected in the canonical contract.

These gated states are governance-complete states, not production-readiness claims.

## Strict invariant

`--strict` rejects every UNKNOWN, MISSING, TBD, and TODO cell. It also rejects a VERIFIED provider when an implementation/evidence column says it is inactive or not implemented.

## Run

`python scripts/verify_integration_certificate.py --strict`

CI runs the same command in the P0 conformance workflow.