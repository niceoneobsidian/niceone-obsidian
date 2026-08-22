from ois.kernel import JsonFileCheckpointStore


def test_durable_checkpoint_is_public_kernel_api():
    assert JsonFileCheckpointStore is not None
