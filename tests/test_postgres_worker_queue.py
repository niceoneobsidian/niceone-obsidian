from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest

from ois.kernel import LeaseLost
from ois.runtime import PostgreSQLWorkerQueue

DSN = os.getenv("OIS_POSTGRES_DSN")
pytestmark = pytest.mark.skipif(not DSN, reason="OIS_POSTGRES_DSN is not configured")


def queue() -> PostgreSQLWorkerQueue:
    assert DSN
    return PostgreSQLWorkerQueue(DSN)


def test_queue_round_trip_and_retry() -> None:
    q = queue()
    job_id = f"queue-{uuid4()}"
    queued = q.enqueue(job_id, "conformance", {"value": "hello"})
    assert queued.status == "queued"
    assert queued.attempts == 0

    claimed = q.claim("conformance", "worker-a")
    assert claimed is not None
    assert claimed.lease_owner == "worker-a"
    assert claimed.lease_epoch is not None

    retried = q.retry(job_id, "worker-a", claimed.lease_epoch)
    assert retried.status == "queued"
    assert retried.attempts == 1
    assert retried.lease_owner is None

    claimed_again = q.claim("conformance", "worker-b")
    assert claimed_again is not None
    assert claimed_again.lease_epoch is not None
    assert claimed_again.lease_epoch > claimed.lease_epoch

    completed = q.acknowledge(job_id, "worker-b", claimed_again.lease_epoch)
    assert completed.status == "completed"


def test_only_one_worker_claims_a_job_concurrently() -> None:
    q = queue()
    job_id = f"queue-concurrency-{uuid4()}"
    q.enqueue(job_id, "concurrency", {"value": 1})

    def claim(worker_id: str):
        return q.claim("concurrency", worker_id)

    with ThreadPoolExecutor(max_workers=8) as pool:
        claimed = list(pool.map(claim, [f"worker-{i}" for i in range(8)]))

    winners = [job for job in claimed if job is not None]
    assert len(winners) == 1
    assert winners[0].job_id == job_id


def test_expired_queue_lease_is_reclaimed_with_new_fencing_epoch() -> None:
    q = queue()
    job_id = f"queue-reclaim-{uuid4()}"
    q.enqueue(job_id, "reclaim", {"value": "recover"})

    stale = q.claim("reclaim", "worker-a", ttl_seconds=-1)
    assert stale is not None
    assert stale.lease_epoch is not None

    current = q.claim("reclaim", "worker-b", ttl_seconds=30)
    assert current is not None
    assert current.lease_epoch is not None
    assert current.lease_epoch > stale.lease_epoch

    with pytest.raises(LeaseLost):
        q.acknowledge(job_id, "worker-a", stale.lease_epoch)

    completed = q.acknowledge(job_id, "worker-b", current.lease_epoch)
    assert completed.status == "completed"


def test_stale_worker_cannot_retry_after_takeover() -> None:
    q = queue()
    job_id = f"queue-fence-{uuid4()}"
    q.enqueue(job_id, "fence", {"value": "stale"})

    stale = q.claim("fence", "worker-a", ttl_seconds=-1)
    assert stale is not None
    current = q.claim("fence", "worker-b", ttl_seconds=30)
    assert current is not None

    with pytest.raises(LeaseLost):
        q.retry(job_id, "worker-a", stale.lease_epoch or 0)

    q.acknowledge(job_id, "worker-b", current.lease_epoch or 0)
