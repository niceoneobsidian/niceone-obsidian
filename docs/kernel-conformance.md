# Phase 2: Kernel Conformance

Phase 2 makes the kernel evidence boundary executable. The conformance suite is intentionally small and deterministic so it can run without PostgreSQL, Redis, network access, or external credentials.

## Contract enforced

- Evidence events are immutable after construction.
- Event serialization contains stable execution and event identifiers.
- Ledgers append evidence and return immutable snapshots.
- Evidence reads are scoped by execution identifier.
- SQLite persistence preserves append order and is idempotent by event identifier.
- Invalid payloads fail closed instead of being silently accepted.

## Gate

The `kernel-conformance` CI check runs `tests/governance/test_kernel_conformance.py` with bytecode compilation. Phase 2 is complete only when the suite passes on a clean runner and the contract remains represented by executable tests.

This phase does not claim PostgreSQL, Redis, recovery, tenant isolation, or external API conformance. Those remain later gates in the canonical sequence.
