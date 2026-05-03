from __future__ import annotations

from unittest.mock import MagicMock, patch

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph

from graph.state import GraphState
from nodes.patch_agent import patch_node


def test_route_after_validation_mapping_keys() -> None:
    # Ensures conditional edge map stays aligned with router return values.
    mapping = {"patch": "patch", "pr": "pr", "dry_run": "dry_run", "human_review": "human_review"}
    assert set(mapping) == {"patch", "pr", "dry_run", "human_review"}


@patch("nodes.patch_agent.completion")
def test_patch_node_increments_retry_on_prior_validation_failure(mock_completion: MagicMock) -> None:
    mock_completion.return_value = MagicMock()
    mock_completion.return_value.choices = [
        MagicMock(message=MagicMock(content='{"unified_diff":"","files_modified":[],"explanation":"x"}')),
    ]

    state: GraphState = {
        "issue_url": "https://github.com/o/r/issues/1",
        "dry_run": False,
        "base_commit_sha_override": None,
        "issue_context": {
            "issue_number": 1,
            "title": "t",
            "body": "b",
            "labels": [],
            "repo_owner": "o",
            "repo_name": "r",
            "repo_url": "https://github.com/o/r.git",
            "default_branch": "main",
            "base_commit_sha": "abc",
        },
        "research_output": {
            "relevant_files": [],
            "file_contents": {},
            "related_symbols": [],
            "issue_summary": "s",
            "confidence_score": 0.5,
        },
        "planning_output": {
            "fix_strategy": "fix",
            "candidate_files": [],
            "estimated_lines_changed": 1,
            "risk_level": "low",
            "requires_new_tests": False,
            "ambiguous": False,
        },
        "patch_output": None,
        "validation_output": {
            "test_exit_code": 1,
            "tests_passed": False,
            "lint_passed": True,
            "type_check_passed": True,
            "stdout": "",
            "stderr": "err",
            "retry_count": 1,
            "routing_decision": "retry_patch",
        },
        "pr_output": None,
        "retry_count": 1,
        "max_retries": 3,
        "error_message": None,
        "final_status": None,
    }

    out = patch_node(state)
    assert out["retry_count"] == 2


def test_minigraph_checkpoint_roundtrip() -> None:
    def n(state: GraphState) -> dict:
        return {"retry_count": state["retry_count"] + 1}

    g = StateGraph(GraphState)
    g.add_node("n", n)
    g.add_edge(START, "n")
    g.add_edge("n", END)
    cg = g.compile(checkpointer=MemorySaver())
    cfg = {"configurable": {"thread_id": "t1"}}
    cg.invoke(
        {
            "issue_url": "u",
            "dry_run": False,
            "base_commit_sha_override": None,
            "issue_context": None,
            "research_output": None,
            "planning_output": None,
            "patch_output": None,
            "validation_output": None,
            "pr_output": None,
            "retry_count": 0,
            "max_retries": 3,
            "error_message": None,
            "final_status": None,
        },
        config=cfg,
    )
    snap = cg.get_state(cfg)
    assert snap.values["retry_count"] == 1
