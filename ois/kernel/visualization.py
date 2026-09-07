"""Governed visualization helpers for the OIS execution graph.

The visualizer is deliberately an observation/documentation boundary. It does
not execute, authorize, or mutate a workflow.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any


class OISGraphVisualizer:
    """Export a compiled LangGraph topology without making it authoritative."""

    @staticmethod
    def export_layout_to_mermaid(
        compiled_graph: Any,
        output_filepath: str = "ois_kernel_layout.md",
    ) -> str:
        """Write the runtime graph topology as a Mermaid Markdown document."""
        graph = compiled_graph.get_graph()
        if hasattr(graph, "draw_mermaid"):
            mermaid_code = graph.draw_mermaid()
        elif hasattr(graph, "to_mermaid"):
            mermaid_code = graph.to_mermaid()
        else:
            raise TypeError("compiled graph does not expose a Mermaid renderer")

        wrapped_markdown = f"```mermaid\n{mermaid_code}\n```\n"
        Path(output_filepath).write_text(wrapped_markdown, encoding="utf-8")
        return wrapped_markdown

    @staticmethod
    def save_layout_as_png(
        compiled_graph: Any,
        output_filepath: str = "ois_kernel_layout.png",
    ) -> None:
        """Render the graph through LangGraph's Mermaid PNG renderer."""
        graph = compiled_graph.get_graph()
        renderer = getattr(graph, "draw_mermaid_png", None)
        if renderer is None:
            raise RuntimeError("compiled graph does not expose draw_mermaid_png")
        png_bytes = renderer()
        Path(output_filepath).write_bytes(png_bytes)
