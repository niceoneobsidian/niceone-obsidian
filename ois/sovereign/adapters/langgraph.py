"""LangGraph adapter.

LangGraph supplies agent/workflow orchestration; OIS remains the authority for
request contracts, policy, registries, evidence and activation.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from ..contracts import ExecutionRequest, ExecutionResult, ExecutionState


class LangGraphBackend:
    name = "langgraph"

    def __init__(self, graph: Any) -> None:
        self.graph = graph

    @classmethod
    def from_nodes(cls, nodes: Mapping[str, Callable[[dict[str, Any]], dict[str, Any]]], edges: list[tuple[str, str]]) -> "LangGraphBackend":
        try:
            from langgraph.graph import END, START, StateGraph
        except ImportError as exc:
            raise RuntimeError("LangGraph adapter requires the 'langgraph' package") from exc

        builder = StateGraph(dict[str, Any])
        for name, node in nodes.items():
            builder.add_node(name, node)
        if nodes:
            first = next(iter(nodes))
            builder.add_edge(START, first)
        for source, target in edges:
            builder.add_edge(source, END if target == "__end__" else target)
        return cls(builder.compile())

    def execute(self, request: ExecutionRequest) -> ExecutionResult:
        try:
            output = self.graph.invoke({"input": request.input, "execution_id": request.execution_id})
            return ExecutionResult(request.execution_id, ExecutionState.SUCCEEDED, output=output,
                                   evidence={"orchestrator": self.name})
        except Exception as exc:
            return ExecutionResult(request.execution_id, ExecutionState.FAILED, error=str(exc),
                                   evidence={"orchestrator": self.name})
