from __future__ import annotations

from ois.integration.spine import OISSpine
from ois.kernel.idempotency import InMemoryIdempotencyStore
from ois.kernel.recovery import RecoveryPolicy
from ois.registries import CapabilityRegistry


def test_spine_passes_explicit_idempotency_and_recovery_policies_to_runtime() -> None:
    idempotency = InMemoryIdempotencyStore()
    recovery = RecoveryPolicy(max_retries=1, max_recovery_attempts=1)

    spine = OISSpine(
        CapabilityRegistry(),
        idempotency=idempotency,
        recovery=recovery,
    )

    assert spine.runtime.idempotency is idempotency
    assert spine.runtime.recovery is recovery
