from __future__ import annotations

import json

from production.argo_canary_gate import EvidenceArtifact


def test_canary_evidence_is_append_only_and_hash_linked(tmp_path) -> None:
    path = tmp_path / "evidence.jsonl"
    ledger = EvidenceArtifact(str(path))

    first = ledger.append("rollout.canary.started", {"traffic_percent": 10})
    second = ledger.append("rollout.canary.failed", {"phase": "Degraded"})

    assert first != second
    records = [json.loads(line) for line in path.read_text().splitlines()]
    assert len(records) == 2
    assert records[0]["previous_hash"] is None
    assert records[1]["previous_hash"] == records[0]["content_hash"]
    assert records[0]["content_hash"] != records[1]["content_hash"]


def test_canary_evidence_flushes_to_disk(tmp_path) -> None:
    path = tmp_path / "evidence.jsonl"
    ledger = EvidenceArtifact(str(path))
    ledger.append("rollout.canary.timeout", {"max_checks": 20})

    assert path.exists()
    assert path.read_text(encoding="utf-8").count("rollout.canary.timeout") == 1
