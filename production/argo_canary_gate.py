"""Evidence-gated Argo Rollouts monitor for the OIS kernel canary.

The gate observes the Argo Rollout status; it never promotes a rollout itself.
Argo Rollouts remains the deployment authority. The gate records an append-only
forensic evidence artifact for later ingestion by the canonical OIS evidence
ledger and fails closed on timeout, degradation, or abort.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from kubernetes_asyncio import client, config
from kubernetes_asyncio.client.exceptions import ApiException


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _hash_event(event: dict[str, Any], previous_hash: str | None) -> str:
    canonical = json.dumps(
        {"event": event, "previous_hash": previous_hash},
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


class EvidenceArtifact:
    """Append-only local evidence artifact with a hash-linked event chain."""

    def __init__(self, path: str | None = None) -> None:
        self.path = Path(path or os.getenv("OIS_CANARY_EVIDENCE_PATH", "/tmp/ois-canary-evidence.jsonl"))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.previous_hash: str | None = None
        if self.path.exists():
            lines = self.path.read_text(encoding="utf-8").splitlines()
            if lines:
                self.previous_hash = json.loads(lines[-1])["content_hash"]

    def append(self, event_type: str, payload: dict[str, Any]) -> str:
        event = {
            "event_id": hashlib.sha256(f"{_now()}:{event_type}:{json.dumps(payload, sort_keys=True)}".encode()).hexdigest()[:32],
            "timestamp": _now(),
            "event_type": event_type,
            "payload": payload,
        }
        content_hash = _hash_event(event, self.previous_hash)
        record = {**event, "previous_hash": self.previous_hash, "content_hash": content_hash}
        with self.path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        self.previous_hash = content_hash
        return record["event_id"]


class CanaryRolloutMonitor:
    def __init__(self, name: str, namespace: str, evidence: EvidenceArtifact) -> None:
        self.name = name
        self.namespace = namespace
        self.evidence = evidence
        self.custom_api: client.CustomObjectsApi | None = None

    async def run(self, poll_interval_s: int, max_checks: int) -> int:
        await config.load_incluster_config()
        self.custom_api = client.CustomObjectsApi()
        self.evidence.append(
            "rollout.canary.monitor.started",
            {"rollout": self.name, "namespace": self.namespace, "max_checks": max_checks},
        )

        for check in range(1, max_checks + 1):
            try:
                assert self.custom_api is not None
                rollout = await self.custom_api.get_namespaced_custom_object(
                    group="argoproj.io",
                    version="v1alpha1",
                    namespace=self.namespace,
                    plural="rollouts",
                    name=self.name,
                )
                status = rollout.get("status", {})
                phase = status.get("phase", "Unknown")
                step = status.get("currentStepIndex")
                conditions = status.get("conditions", [])
                self.evidence.append(
                    "rollout.canary.observed",
                    {"rollout": self.name, "check": check, "phase": phase, "step": step, "conditions": conditions},
                )

                if phase in {"Degraded", "Aborted"}:
                    self.evidence.append(
                        "rollout.canary.failed",
                        {"rollout": self.name, "phase": phase, "step": step},
                    )
                    return 1

                if phase == "Healthy" and status.get("currentStepIndex") is not None:
                    self.evidence.append(
                        "rollout.canary.healthy",
                        {"rollout": self.name, "step": step},
                    )
                    return 0

            except ApiException as exc:
                self.evidence.append(
                    "rollout.canary.api_error",
                    {"rollout": self.name, "check": check, "status": exc.status, "reason": exc.reason},
                )

            await asyncio.sleep(poll_interval_s)

        self.evidence.append(
            "rollout.canary.timeout",
            {"rollout": self.name, "max_checks": max_checks},
        )
        return 2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Monitor an OIS Argo Rollout and emit forensic evidence")
    parser.add_argument("--name", default="ois-hardened-worker-node")
    parser.add_argument("--namespace", default="ois-worker-sandbox")
    parser.add_argument("--poll-interval", type=int, default=20)
    parser.add_argument("--max-checks", type=int, default=20)
    parser.add_argument("--evidence-path", default=None)
    return parser.parse_args()


async def _main() -> int:
    args = parse_args()
    evidence = EvidenceArtifact(args.evidence_path)
    monitor = CanaryRolloutMonitor(args.name, args.namespace, evidence)
    return await monitor.run(args.poll_interval, args.max_checks)


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
