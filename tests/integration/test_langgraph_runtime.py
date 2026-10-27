from __future__ import annotations

from types import SimpleNamespace
from typing import Any, cast

import pytest
from langgraph.checkpoint.memory import MemorySaver

from ois.integration.langgraph_runtime import build_ois_graph
from ois.integration.spine import OISSpine, SpineRequest


class RecordingSpine:
    def __init__(self) -> None:
        self.calls: list[tuple[SpineRequest, str | None]] = []

    def submit(
        self,
        request: SpineRequest,
        *,
        invocation_id: str | None = None,
    ) -> Any:
        self.calls.append((request, invocation_id))
        return SimpleNamespace(
            execution_id="execution-1",
            invocation_id=invocation_id or "generated-invocation",
            status="succeeded",
            output={"accepted": True},
            error=None,
        )


def _request() -> SpineRequest:
    return SpineRequest(
        objective="verify LangGraph adapter",
        capability_id="test.capability",
        capability_version="1",
        tenant_id="tenant-test",
    )


def test_graph_propagates_invocation_id_to_governed_spine() -> None:
    spine = RecordingSpine()
    graph = build_ois_graph(cast(OISSpine, spine))

    result = graph.invoke({"request": _request(), "invocation_id": "invocation-stable-1"})

    assert spine.calls == [(_request(), "invocation-stable-1")]
    assert result["execution_id"] == "execution-1"
    assert result["invocation_id"] == "invocation-stable-1"
    assert result["status"] == "succeeded"


def test_graph_preserves_checkpointed_result_for_thread() -> None:
    spine = RecordingSpine()
    checkpointer = MemorySaver()
    config = {"configurable": {"thread_id": "langgraph-recovery-test"}}
    graph = build_ois_graph(cast(OISSpine, spine), checkpointer=checkpointer)

    graph.invoke(
        {"request": _request(), "invocation_id": "invocation-checkpoint-1"},
        config=config,
    )

    # Rebuild the compiled graph around the same checkpoint store to verify
    # state is graph-independent. This is not a process-restart durability test.
    restarted_graph = build_ois_graph(cast(OISSpine, spine), checkpointer=checkpointer)
    saved = restarted_graph.get_state(config)

    assert saved.values["execution_id"] == "execution-1"
    assert saved.values["invocation_id"] == "invocation-checkpoint-1"
    assert saved.values["status"] == "succeeded"
    assert len(spine.calls) == 1


def test_graph_rejects_missing_request_before_spine_submission() -> None:
    spine = RecordingSpine()
    graph = build_ois_graph(cast(OISSpine, spine))

    with pytest.raises(ValueError, match="missing a request"):
        graph.invoke({})

    assert spine.calls == []
