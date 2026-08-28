from ois.runtime.execution_backend import (
    SQLiteExecutionStore,
    SQLiteWorkerQueue,
)


def test_execution_store_checkpoint_resume_and_complete() -> None:
    store = SQLiteExecutionStore()
    store.create("exec-1", "workflow-1", {"input": "value"})
    store.checkpoint("exec-1", {"node": "research", "output": "evidence"})

    resumed = store.get("exec-1")
    assert resumed.status == "running"
    assert resumed.checkpoint == {"node": "research", "output": "evidence"}

    completed = store.complete("exec-1", {"answer": "done"})
    assert completed.status == "succeeded"
    assert completed.result == {"answer": "done"}


def test_worker_queue_claim_retry_and_acknowledge() -> None:
    queue = SQLiteWorkerQueue()
    queue.enqueue("job-1", "default", {"task": "run"})

    claimed = queue.claim("default", "worker-1")
    assert claimed is not None
    assert claimed.lease_owner == "worker-1"
    assert claimed.attempts == 0

    retried = queue.retry("job-1", "worker-1")
    assert retried.attempts == 1
    assert retried.lease_owner is None

    claimed_again = queue.claim("default", "worker-2")
    assert claimed_again is not None
    completed = queue.acknowledge("job-1", "worker-2")
    assert completed.lease_owner == "worker-2"
