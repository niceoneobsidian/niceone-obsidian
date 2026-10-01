from ois.kernel import Supervisor, SupervisorRequest


def test_supervisor_is_public_kernel_api():  # type: ignore
    assert Supervisor is not None
    assert SupervisorRequest is not None
