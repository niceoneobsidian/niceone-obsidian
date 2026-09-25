from ois.kernel import JsonFileCheckpointStore


def test_durable_checkpoint_is_public_kernel_api():  # type: ignore
    assert JsonFileCheckpointStore is not None
