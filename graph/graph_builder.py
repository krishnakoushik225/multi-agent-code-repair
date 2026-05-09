from __future__ import annotations

import sqlite3
from pathlib import Path

from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, START, StateGraph

from graph.edges import route_after_ingestion, route_after_planning, route_after_validation
from graph.state import GraphState
from nodes.dry_run_node import dry_run_node
from nodes.failed_node import failed_node
from nodes.human_review_node import human_review_node
from nodes.ingestion import ingestion_node
from nodes.patch_agent import patch_node
from nodes.planning_agent import planning_node
from nodes.pr_node import pr_node
from nodes.research_agent import research_node
from nodes.validation_node import validation_node

# Explicit allowlist: SAFE_MSGPACK_TYPES are still accepted first by the serde hook.
_CHECKPOINT_MSGPACK_TYPES: tuple[tuple[str, str], ...] = (
    ("graph.state", "IssueContext"),
    ("graph.state", "ResearchOutput"),
    ("graph.state", "RiskLevel"),
    ("graph.state", "PlanningOutput"),
    ("graph.state", "FileChange"),
    ("graph.state", "PatchOutput"),
    ("graph.state", "RoutingDecision"),
    ("graph.state", "ValidationOutput"),
    ("graph.state", "PROutput"),
)


def build_graph():
    graph = StateGraph(GraphState)

    graph.add_node("ingestion", ingestion_node)
    graph.add_node("research", research_node)
    graph.add_node("planning", planning_node)
    graph.add_node("patch", patch_node)
    graph.add_node("validation", validation_node)
    graph.add_node("pr", pr_node)
    graph.add_node("dry_run", dry_run_node)
    graph.add_node("human_review", human_review_node)
    graph.add_node("failed", failed_node)

    graph.add_edge(START, "ingestion")
    graph.add_conditional_edges(
        "ingestion",
        route_after_ingestion,
        {"research": "research", "failed": "failed"},
    )
    graph.add_edge("research", "planning")
    graph.add_conditional_edges(
        "planning",
        route_after_planning,
        {"patch": "patch", "human_review": "human_review"},
    )
    graph.add_edge("patch", "validation")
    graph.add_conditional_edges(
        "validation",
        route_after_validation,
        {
            "patch": "patch",
            "pr": "pr",
            "dry_run": "dry_run",
            "human_review": "human_review",
        },
    )
    graph.add_edge("pr", END)
    graph.add_edge("dry_run", END)
    graph.add_edge("human_review", END)
    graph.add_edge("failed", END)

    checkpoints_dir = Path(__file__).resolve().parent.parent / "checkpoints"
    checkpoints_dir.mkdir(parents=True, exist_ok=True)
    db_path = checkpoints_dir / "graph.db"
    conn = sqlite3.connect(str(db_path), check_same_thread=False)
    serde = JsonPlusSerializer(allowed_msgpack_modules=_CHECKPOINT_MSGPACK_TYPES)
    checkpointer = SqliteSaver(conn, serde=serde)

    return graph.compile(checkpointer=checkpointer)
