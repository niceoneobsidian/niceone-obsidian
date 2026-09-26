from ois.kernel import (
    ExecutionContext,
    ExecutionIdentity,
    JsonFileCheckpointStore,
)


def make_context():  # type: ignore
    return ExecutionContext(
        identity=ExecutionIdentity(
            tenant_id="tenant-durable-test",
        ),
        objective="Durable checkpoint integration test",
    )


def test_json_checkpoint_store_persists_execution(tmp_path):  # type: ignore
    store = JsonFileCheckpointStore(str(tmp_path / "checkpoints"))

    context = make_context()
    context.working_memory["answer"] = {"value": 42}

    store.save(context)

    assert store.exists(context.identity.execution_id)

    restored = store.load(context.identity.execution_id)

    assert restored.identity.execution_id == context.identity.execution_id
    assert restored.identity.tenant_id == context.identity.tenant_id
    assert restored.objective == context.objective
    assert restored.working_memory["answer"] == {"value": 42}


def test_json_checkpoint_survives_store_recreation(tmp_path):  # type: ignore
    checkpoint_path = tmp_path / "checkpoints"

    first_store = JsonFileCheckpointStore(str(checkpoint_path))

    context = make_context()
    context.working_memory["survives_restart"] = True

    first_store.save(context)

    second_store = JsonFileCheckpointStore(str(checkpoint_path))

    restored = second_store.load(context.identity.execution_id)

    assert restored.working_memory["survives_restart"] is True


def test_json_checkpoint_missing_execution_raises(tmp_path):  # type: ignore
    from ois.kernel import CheckpointNotFound

    store = JsonFileCheckpointStore(str(tmp_path / "checkpoints"))

    try:
        store.load("missing-execution")  # type: ignore
    except CheckpointNotFound:
        pass
    else:
        raise AssertionError("Expected CheckpointNotFound")
