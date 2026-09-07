from __future__ import annotations

import asyncio
import json
import secrets
from dataclasses import dataclass
from typing import Any


class SandboxConfigurationError(RuntimeError):
    """Raised when the Kubernetes/gVisor sandbox cannot be configured."""


class SandboxExecutionError(RuntimeError):
    """Raised when an isolated execution fails."""


@dataclass(frozen=True)
class SandboxResult:
    execution_id: str
    phase: str
    logs: str


class KubernetesGVisorSandbox:
    """Ephemeral Kubernetes execution boundary using a gVisor RuntimeClass.

    Kubernetes dependencies are optional at import time so the core kernel remains
    usable without a cluster. The runner reads its payload from a mounted Secret,
    avoiding command-line exposure of tool arguments.
    """

    def __init__(
        self,
        *,
        namespace: str = "ois-worker-sandbox",
        runtime_class: str = "gvisor-sandbox",
        runner_image: str = "ois-registry.internal/runner/python-base:v1.0.0",
    ) -> None:
        self.namespace = namespace
        self.runtime_class = runtime_class
        self.runner_image = runner_image
        self._core: Any | None = None
        self._api: Any | None = None

    async def open(self) -> None:
        try:
            from kubernetes_asyncio import client, config
        except ImportError as exc:  # pragma: no cover - exercised in deployment images
            raise SandboxConfigurationError(
                "kubernetes_asyncio is required for Kubernetes sandbox execution"
            ) from exc
        try:
            await config.load_incluster_config()
        except Exception:
            await config.load_kube_config()
        self._core = client.CoreV1Api()
        self._api = client

    async def run(
        self,
        *,
        execution_id: str,
        tool_name: str,
        payload: dict[str, Any],
        timeout_seconds: int = 120,
    ) -> SandboxResult:
        if self._core is None or self._api is None:
            await self.open()
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")

        client = self._api
        suffix = secrets.token_hex(4)
        safe_tool = "".join(ch if ch.isalnum() or ch == "-" else "-" for ch in tool_name.lower())[:32]
        pod_name = f"ois-{safe_tool}-{suffix}"
        secret_name = f"{pod_name}-input"
        encoded_payload = json.dumps(payload, sort_keys=True)

        secret = client.V1Secret(
            metadata=client.V1ObjectMeta(name=secret_name, namespace=self.namespace),
            string_data={"payload.json": encoded_payload},
            type="Opaque",
        )
        pod = client.V1Pod(
            metadata=client.V1ObjectMeta(
                name=pod_name,
                namespace=self.namespace,
                labels={"app": "ois-sandbox", "execution_id": execution_id},
            ),
            spec=client.V1PodSpec(
                runtime_class_name=self.runtime_class,
                restart_policy="Never",
                automount_service_account_token=False,
                security_context=client.V1PodSecurityContext(run_as_non_root=True),
                containers=[
                    client.V1Container(
                        name="runner",
                        image=self.runner_image,
                        command=["python3", "-m", "ois_tool_runner", "--payload-file", "/run/ois/payload.json"],
                        volume_mounts=[client.V1VolumeMount(name="input", mount_path="/run/ois", read_only=True)],
                        resources=client.V1ResourceRequirements(
                            requests={"cpu": "100m", "memory": "64Mi"},
                            limits={"cpu": "200m", "memory": "128Mi"},
                        ),
                        security_context=client.V1SecurityContext(
                            allow_privilege_escalation=False,
                            privileged=False,
                            read_only_root_filesystem=True,
                            capabilities=client.V1Capabilities(drop=["ALL"]),
                        ),
                    )
                ],
                volumes=[
                    client.V1Volume(
                        name="input",
                        secret=client.V1SecretVolumeSource(secret_name=secret_name),
                    )
                ],
            ),
        )

        try:
            await self._core.create_namespaced_secret(self.namespace, secret)
            await self._core.create_namespaced_pod(self.namespace, pod)
            phase = "Pending"
            for _ in range(timeout_seconds * 2):
                status = await self._core.read_namespaced_pod_status(pod_name, self.namespace)
                phase = status.status.phase or "Unknown"
                if phase in {"Succeeded", "Failed"}:
                    break
                await asyncio.sleep(0.5)
            else:
                raise SandboxExecutionError("sandbox execution timed out")

            logs = await self._core.read_namespaced_pod_log(pod_name, self.namespace)
            if phase != "Succeeded":
                raise SandboxExecutionError(f"sandbox exited in phase {phase}: {logs}")
            return SandboxResult(execution_id=execution_id, phase=phase, logs=logs)
        finally:
            for delete in (
                lambda: self._core.delete_namespaced_pod(pod_name, self.namespace, grace_period_seconds=0),
                lambda: self._core.delete_namespaced_secret(secret_name, self.namespace),
            ):
                try:
                    await delete()
                except Exception:
                    pass
