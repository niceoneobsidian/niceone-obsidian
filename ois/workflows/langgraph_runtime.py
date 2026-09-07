from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from typing import Any, TypedDict


class OISGraphState(TypedDict, total=False):
    execution_id: str
    tenant_id: str
    workflow_id: str
    workflow_version: str
    current_state: str
    payload: dict[str, Any]
    error: dict[str, Any]


Node = Callable[[OISGraphState], Awaitable[Mapping[str, Any]]]


class LangGraphUnavailable(RuntimeError):
    """Raised when the optional LangGraph provider is not installed."""


def compile_interruptible_graph(
    *,
    prepare: Node,
    execute: Node,
    validate: Node,
) -> Any:
    """Compile the OIS workflow graph while keeping policy outside LangGraph.

    LangGraph owns durable graph orchestration/checkpoint boundaries; OIS policy,
    authorization, evidence and side-effect admission remain kernel concerns.
    The graph pauses immediately before the validation/admission node so a caller
    can resume only after its own HITL decision has been durably recorded.
    """
    try:
        from langgraph.graph import END, START, StateGraph
    except ImportError as exc:  # pragma: no cover - provider dependency
        raise LangGraphUnavailable(
            "Install the LangGraph provider to activate this orchestration adapter"
        ) from exc

    graph = StateGraph(OISGraphState)
    graph.add_node("prepare", prepare)
    graph.add_node("execute", execute)
    graph.add_node("validate", validate)
    graph.add_edge(START, "prepare")
    graph.add_edge("prepare", "execute")
    graph.add_edge("execute", "validate")
    graph.add_edge("validate", END)
    return graph.compile(interrupt_before=["validate"])
