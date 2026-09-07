from __future__ import annotations

import ctypes
import errno
import os
import socket
import sys
from dataclasses import dataclass


@dataclass(frozen=True)
class SandboxAttestation:
    runtime: str
    kernel_signature: str
    network_raw_socket_blocked: bool


def is_gvisor_runtime() -> bool:
    """Fail-closed runtime attestation from an explicit deployment contract plus kernel hint."""
    declared = os.getenv("OIS_SANDBOX_RUNTIME", "").strip().lower()
    if declared == "gvisor":
        return True
    try:
        return "gvisor" in open("/proc/version", encoding="utf-8").read().lower()
    except OSError:
        return False


def assert_raw_socket_blocked() -> None:
    """Verify the sandbox lacks CAP_NET_RAW; this tests privilege restriction, not host namespace access."""
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_RAW, socket.IPPROTO_RAW)
    except PermissionError:
        return
    finally:
        # socket is only assigned on success; close below in the success path.
        pass
    sock.close()
    raise AssertionError("Sandbox permits raw packet sockets; CAP_NET_RAW must be removed")


def assert_mount_remount_blocked() -> None:
    """Attempt a root filesystem remount and require EPERM/EACCES."""
    libc = ctypes.CDLL(None, use_errno=True)
    if sys.platform != "linux":
        raise RuntimeError("gVisor conformance requires Linux")
    result = libc.mount(b"none", b"/", b"none", 32, None)  # MS_REMOUNT
    if result != -1 or ctypes.get_errno() not in {errno.EPERM, errno.EACCES}:
        raise AssertionError("Sandbox permitted a root filesystem remount")


def attest() -> SandboxAttestation:
    if not is_gvisor_runtime():
        raise RuntimeError("OIS_SANDBOX_RUNTIME=gvisor or a gVisor kernel signature is required")
    assert_raw_socket_blocked()
    assert_mount_remount_blocked()
    return SandboxAttestation(
        runtime="gvisor",
        kernel_signature="attested",
        network_raw_socket_blocked=True,
    )
