"""Fail-closed live Sportmonks source verification."""

from __future__ import annotations

import os
import sys

from ois.infrastructure.source_adapters import SportmonksFootballAdapter
from ois.infrastructure.source_gateway import (
    InMemoryCredentialResolver,
    SQLiteSourceLedger,
    SourceGateway,
)


def main() -> int:
    token = os.getenv("SPORTMONKS_API_TOKEN")
    if not token:
        print("LIVE_SOURCE_UNVERIFIED: SPORTMONKS_API_TOKEN is not configured")
        return 2

    ledger = SQLiteSourceLedger()
    gateway = SourceGateway(
        credentials=InMemoryCredentialResolver({"sportmonks-live": token}),
        evidence=ledger,
        outbox=ledger,
    )
    adapter = SportmonksFootballAdapter()
    result = adapter.ingest(
        tenant_id=os.getenv("OIS_VERIFY_TENANT", "live-verification"),
        workspace_id=os.getenv("OIS_VERIFY_WORKSPACE", "sportmonks"),
        gateway=gateway,
        credential_id="sportmonks-live",
    )
    if result.records < 1:
        print("LIVE_SOURCE_FAILED: Sportmonks returned no accepted source records")
        return 1
    evidence = ledger.evidence(result.evidence_ids[0])
    if evidence is None or not ledger.pending():
        print("LIVE_SOURCE_FAILED: evidence/outbox proof is incomplete")
        return 1
    print(
        f"LIVE_SOURCE_VERIFIED: source={adapter.source_id} records={result.records} "
        f"evidence_id={result.evidence_ids[0]} payload_hash={result.payload_hashes[0]}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
