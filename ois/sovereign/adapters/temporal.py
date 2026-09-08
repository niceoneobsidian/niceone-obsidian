"""Temporal durability candidate boundary.

Temporal is intentionally not the OIS authority. It may own durable workflow
coordination while OIS owns policy, authorization, contracts and evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class TemporalWorkflowRef:
    workflow_id: str
    run_id: str | None = None
    task_queue: str = "ois"


class TemporalDurabilityCandidate:
    """Thin integration seam; activation requires an explicit durability gate."""

    name = "temporal"

    def __init__(self, client: Any) -> None:
        self.client = client

    async def start(self, workflow: Any, *, workflow_id: str, task_queue: str, args: list[Any] | None = None) -> TemporalWorkflowRef:
        """Start an OIS-owned workflow through a Temporal client."""
        handle = await self.client.start_workflow(
            workflow,
            *(args or []),
            id=workflow_id,
            task_queue=task_queue,
        )
        return TemporalWorkflowRef(workflow_id=workflow_id, run_id=handle.run_id, task_queue=task_queue)

    async def result(self, workflow_id: str) -> Any:
        """Retrieve a durable workflow result without changing OIS policy state."""
        handle = self.client.get_workflow_handle(workflow_id)
        return await handle.result()
