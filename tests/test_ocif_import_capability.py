from __future__ import annotations

import tempfile
from pathlib import Path
from types import SimpleNamespace

from ois.integration.ocif_import import OCIFImportCapability
from ois.integration.spine import OISSpine, SpineRequest
from ois.kernel.checkpoint import SQLiteCheckpointStore
from ois.kernel.evidence import SQLiteEvidenceLedger
from ois.kernel.idempotency import SQLiteIdempotencyStore
from ois.kernel.policy import DefaultPolicyEngine
from ois.registries import CapabilityRegistry


def _request() -> SpineRequest:
    return SpineRequest(
        objective="Import evidence under explicit policy",
        capability_id="ocif.import.consume",
        capability_version="1.0.0",
        tenant_id="tenant-test",
        input={
            "payload": {
                "contract_version": "0.1.0",
                "source_id": "source-1",
                "capture_id": "capture-1",
            }
        },
    )


def test_denied_ocif_import_never_calls_consumer() -> None:
    calls: list[dict] = []
    capability = OCIFImportCapability(
        lambda payload: (
            calls.append(dict(payload))
            or SimpleNamespace(status="accepted", source_id="source-1", capture_id="capture-1")
        )
    )
    registry = CapabilityRegistry()
    registry.register(capability)
    spine = OISSpine(registry, policy=DefaultPolicyEngine(allowed_permissions=()))

    result = spine.submit(_request(), invocation_id="ocif-denied-stable-id")

    assert result.status == "denied"
    assert calls == []


def test_authorized_ocif_import_uses_durable_idempotency_across_restart() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        calls: list[dict] = []

        def importer(payload):
            calls.append(dict(payload))
            return SimpleNamespace(
                status="accepted",
                source_id="source-1",
                capture_id="capture-1",
                observation_id=17,
                reason=None,
            )

        def make_spine():
            registry = CapabilityRegistry()
            registry.register(OCIFImportCapability(importer))
            return OISSpine(
                registry,
                checkpoint_store=SQLiteCheckpointStore(str(root / "checkpoints.sqlite")),
                evidence=SQLiteEvidenceLedger(str(root / "evidence.sqlite")),
                idempotency=SQLiteIdempotencyStore(str(root / "idempotency.sqlite")),
                policy=DefaultPolicyEngine(allowed_permissions=("ocif.evidence.import",)),
            )

        first = make_spine().submit(_request(), invocation_id="ocif-replay-stable-id")
        second = make_spine().submit(_request(), invocation_id="ocif-replay-stable-id")

        assert first.status == "succeeded"
        assert second.status == "succeeded"
        assert len(calls) == 1
        assert first.output["observation_id"] == 17
        assert second.output["observation_id"] == 17
