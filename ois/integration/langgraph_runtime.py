"""LangGraph adapter around the OIS governed execution spine.

LangGraph owns graph scheduling/checkpoint integration; OIS owns authority,
capability resolution, policy, validation, recovery, and evidence.
"""

from __future__ import annotations

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


def build_ois_graph(spine: OISSpine):
    """Build the canonical single-capability OIS graph.

    This adapter intentionally contains no direct tool/model authority.
    """

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
    return graph.compile()
