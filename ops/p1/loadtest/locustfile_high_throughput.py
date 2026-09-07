import os
import random
import uuid

from locust import HttpUser, between, task

TENANT_POOL = [
    x.strip()
    for x in os.getenv("OIS_STRESS_TENANTS", "").split(",")
    if x.strip()
]
EXECUTION_PATH = os.getenv("OIS_EXECUTION_PATH", "/v1/kernel/execute")
HITL_PATH = os.getenv("OIS_HITL_PATH", "/v1/control-plane/hitl/resolve")

if not TENANT_POOL:
    raise RuntimeError("OIS_STRESS_TENANTS must contain synthetic staging tenant IDs")


class OISKernelStressUser(HttpUser):
    """Synthetic multi-tenant traffic; staging-only credentials must be supplied by env."""

    wait_time = between(0.01, 0.10)

    def on_start(self) -> None:
        self.tenant_id = random.choice(TENANT_POOL)
        token_prefix = os.getenv("OIS_STRESS_TOKEN_PREFIX", "")
        if not token_prefix:
            raise RuntimeError("OIS_STRESS_TOKEN_PREFIX must be configured")
        self.headers = {
            "Authorization": f"Bearer {token_prefix}{self.tenant_id[:8]}",
            "Content-Type": "application/json",
            "X-OIS-Test-Run": os.getenv("OIS_TEST_RUN_ID", "p1-local"),
        }

    @task(3)
    def trigger_high_frequency_execution(self) -> None:
        payload = {
            "thread_id": f"stress-th-{uuid.uuid4().hex[:12]}",
            "workflow_name": "production_high_throughput_load_test",
            "execution_parameters": {
                "batch_id": random.randint(1000, 9999),
                "payload_complexity_factor": 4.5,
            },
        }
        with self.client.post(
            EXECUTION_PATH,
            json=payload,
            headers=self.headers,
            name="kernel_execute",
            catch_response=True,
        ) as response:
            if response.status_code in (200, 202):
                response.success()
            else:
                response.failure(f"kernel execution returned {response.status_code}")

    @task(1)
    def hammer_lock_contention_gate(self) -> None:
        payload = {
            "thread_id": f"contention-th-{random.randint(1, 10)}",
            "gate_id": str(uuid.uuid4()),
            "decision": random.choice(["APPROVED", "REJECTED"]),
        }
        with self.client.post(
            HITL_PATH,
            json=payload,
            headers=self.headers,
            name="hitl_resolve_contention",
            catch_response=True,
        ) as response:
            if response.status_code in (200, 423):
                response.success()
            else:
                response.failure(f"HITL contention returned {response.status_code}")
