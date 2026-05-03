from __future__ import annotations

from graph.state import GraphState


def human_review_node(state: GraphState) -> dict:
    """Terminal node: normalize final_status for human review paths."""
    if state.get("final_status") == "human_review":
        return {}
    return {"final_status": "human_review"}
