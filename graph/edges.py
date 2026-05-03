from __future__ import annotations

from graph.state import GraphState, RiskLevel


def route_after_ingestion(state: GraphState) -> str:
    if state.get("final_status") == "failed" or state.get("error_message"):
        return "failed"
    return "research"


def route_after_planning(state: GraphState) -> str:
    if state.get("final_status") == "human_review":
        return "human_review"
    planning = state.get("planning_output")
    if planning is not None and planning.ambiguous and planning.risk_level == RiskLevel.HIGH:
        return "human_review"
    return "patch"


def route_after_validation(state: GraphState) -> str:
    val = state.get("validation_output")
    if val is None:
        return "human_review"

    if val.tests_passed and val.lint_passed and val.type_check_passed:
        if state.get("dry_run"):
            return "dry_run"
        return "pr"

    if val.retry_count >= state["max_retries"]:
        return "human_review"

    return "patch"
