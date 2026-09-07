from __future__ import annotations

import os

import pytest

from production.sandbox import assert_mount_remount_blocked, assert_raw_socket_blocked, is_gvisor_runtime


@pytest.mark.sandbox
@pytest.mark.skipif(
    os.getenv("OIS_SANDBOX_RUNTIME", "").lower() != "gvisor",
    reason="Run inside a Kubernetes gVisor sandbox with OIS_SANDBOX_RUNTIME=gvisor",
)
def test_gvisor_runtime_attestation() -> None:
    assert is_gvisor_runtime() is True


@pytest.mark.sandbox
@pytest.mark.skipif(
    os.getenv("OIS_SANDBOX_RUNTIME", "").lower() != "gvisor",
    reason="Run inside a Kubernetes gVisor sandbox with OIS_SANDBOX_RUNTIME=gvisor",
)
def test_mount_remount_is_blocked() -> None:
    assert_mount_remount_blocked()


@pytest.mark.sandbox
@pytest.mark.skipif(
    os.getenv("OIS_SANDBOX_RUNTIME", "").lower() != "gvisor",
    reason="Run inside a Kubernetes gVisor sandbox with OIS_SANDBOX_RUNTIME=gvisor",
)
def test_raw_socket_is_blocked() -> None:
    assert_raw_socket_blocked()
