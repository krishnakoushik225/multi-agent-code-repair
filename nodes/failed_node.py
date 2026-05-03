from __future__ import annotations

from graph.state import GraphState


def failed_node(state: GraphState) -> dict:
    """Terminal node after ingestion failure — state already carries error_message/final_status."""
    _ = state
    return {}
