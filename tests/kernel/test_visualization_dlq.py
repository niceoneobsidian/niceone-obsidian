from __future__ import annotations

import json
from uuid import uuid4

from ois.kernel.dlq import OISDeadLetterInterceptor
from ois.kernel.state import ExecutionContext, ExecutionIdentity
from ois.kernel.types import FailureClass
from ois.kernel.visualization import OISGraphVisualizer


class FakeRedisClient:
    def __init__(self) -> None:
        self.lists: dict[str, list[str]] = {}
        self.published: list[tuple[str, str]] = []

    def lpush(self, name: str, *values: str) -> int:
        self.lists.setdefault(name, [])
        self.lists[name][0:0] = list(values)
        return len(self.lists[name])

    def publish(self, channel: str, message: str) -> int:
        self.published.append((channel, message))
        return 1


class FakeRedis:
    def __init__(self) -> None:
        self.client = FakeRedisClient()


class FakeGraph:
    def draw_mermaid(self) -> str:
        return "graph TD\nA --> B"

    def draw_mermaid_png(self) -> bytes:
        return b"PNG"


class FakeCompiledGraph:
    def get_graph(self) -> FakeGraph:
        return FakeGraph()


def test_visualizer_exports_mermaid(tmp_path) -> None:
    output = tmp_path / "layout.md"
    rendered = OISGraphVisualizer.export_layout_to_mermaid(FakeCompiledGraph(), str(output))

    assert "```mermaid" in rendered
    assert "A --> B" in rendered
    assert output.read_text(encoding="utf-8") == rendered


def test_visualizer_exports_png(tmp_path) -> None:
    output = tmp_path / "layout.png"
    OISGraphVisualizer.save_layout_as_png(FakeCompiledGraph(), str(output))

    assert output.read_bytes() == b"PNG"


def test_dlq_quarantine_integrity() -> None:
    redis = FakeRedis()
    state = ExecutionContext(
        identity=ExecutionIdentity(execution_id=uuid4(), tenant_id="tenant-a"),
        objective="execute protected operation",
    )
    state.last_failure = FailureClass.PERMISSION
    state.retry_count = 3
    interceptor = OISDeadLetterInterceptor(redis)

    payload = interceptor.intercept_and_quarantine(
        state,
        "permission denied by policy",
    )

    assert payload.execution_id == str(state.identity.execution_id)
    assert payload.tenant_id == "tenant-a"
    assert payload.fault_type == "permission"
    assert payload.frozen_state_snapshot["retry_count"] == 3
    assert payload.payload_sha256

    raw = redis.client.lists["ois:kernel:dlq:tenant-a"][0]
    decoded = json.loads(raw)
    assert decoded["payload_sha256"] == payload.payload_sha256
    assert redis.client.published[0][0] == "ois:events:escalations"
