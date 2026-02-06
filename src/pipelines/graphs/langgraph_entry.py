"""LangGraph dev entrypoint adapter for the ROB2 workflow."""

from __future__ import annotations

from typing import Any

from pipelines.graphs.rob2_graph import build_rob2_graph


def graph(config: Any = None):
    """Return compiled graph; config is accepted for langgraph runtime compatibility."""
    _ = config
    return build_rob2_graph()
