"""LangGraph adapter around the OIS governed execution spine.

LangGraph owns graph scheduling/checkpoint integration; OIS owns authority,
capability resolution, policy, validation, recovery, and evidence.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from ois.integration.spine import OISSpine, SpineRequest


class OISGraphState(TypedDict, total=False):
    request: SpineRequest
    execution_id: str
    invocation_id: str
    status: str
    output: Any
    error: dict[str, Any] | None


def _builder(spine: OISSpine) -> StateGraph:
    def execute(state: OISGraphState) -> OISGraphState:
        result = spine.submit(state["request"])
        return {
            **state,
            "execution_id": result.execution_id,
            "invocation_id": result.invocation_id,
            "status": result.status,
            "output": result.output,
            "error": dict(result.error) if result.error else None,
        }

    graph = StateGraph(OISGraphState)
    graph.add_node("ois_execute", execute)
    graph.add_edge(START, "ois_execute")
    graph.add_edge("ois_execute", END)
    return graph


def build_ois_graph(spine: OISSpine, *, checkpointer: Any = None) -> Any:
    """Build the canonical OIS graph with an optional durable checkpointer."""
    return _builder(spine).compile(checkpointer=checkpointer)


@contextmanager
def postgres_ois_graph(spine: OISSpine, dsn: str) -> Iterator[Any]:
    """Yield a LangGraph graph using the official PostgreSQL checkpointer."""
    try:
        from langgraph.checkpoint.postgres import PostgresSaver
    except ImportError as exc:  # pragma: no cover - dependency contract
        raise RuntimeError(
            "langgraph-checkpoint-postgres is required for PostgreSQL LangGraph persistence"
        ) from exc

    with PostgresSaver.from_conn_string(dsn) as checkpointer:
        checkpointer.setup()
        yield build_ois_graph(spine, checkpointer=checkpointer)
