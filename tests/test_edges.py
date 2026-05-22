from __future__ import annotations

from graph.edges import route_after_ingestion, route_after_planning, route_after_validation
from graph.state import GraphState, PlanningOutput, RiskLevel, RoutingDecision, ValidationOutput


def _base_state() -> GraphState:
    return {
        "issue_url": "https://github.com/o/r/issues/1",
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
    }


def test_route_after_ingestion_failed() -> None:
    s = _base_state()
    s["error_message"] = "bad"
    assert route_after_ingestion(s) == "failed"


def test_route_after_planning_human_review_high_ambiguous() -> None:
    s = _base_state()
    s["planning_output"] = PlanningOutput(
        fix_strategy="x",
        candidate_files=["a.py"],
        estimated_lines_changed=1,
        risk_level=RiskLevel.HIGH,
        requires_new_tests=False,
        ambiguous=True,
    )
    assert route_after_planning(s) == "human_review"


def test_route_after_validation_routes_to_pr() -> None:
    s = _base_state()
    s["validation_output"] = ValidationOutput(
        test_exit_code=0,
        tests_passed=True,
        lint_passed=True,
        type_check_passed=True,
        stdout="",
        stderr="",
        retry_count=0,
        routing_decision=RoutingDecision.CONTINUE,
    )
    assert route_after_validation(s) == "pr"


def test_route_after_validation_routes_to_dry_run() -> None:
    s = _base_state()
    s["dry_run"] = True
    s["validation_output"] = ValidationOutput(
        test_exit_code=0,
        tests_passed=True,
        lint_passed=True,
        type_check_passed=True,
        stdout="",
        stderr="",
        retry_count=0,
        routing_decision=RoutingDecision.CONTINUE,
    )
    assert route_after_validation(s) == "dry_run"


def test_route_after_validation_retries_then_human() -> None:
    # Routing must read state["retry_count"], not val.retry_count.
    # Set them to different values so only the correct source produces "human_review".
    s = _base_state()
    s["retry_count"] = 3  # source of truth
    s["validation_output"] = ValidationOutput(
        test_exit_code=1,
        tests_passed=False,
        lint_passed=True,
        type_check_passed=True,
        stdout="",
        stderr="boom",
        retry_count=0,  # intentionally wrong — must NOT drive routing
        routing_decision=RoutingDecision.RETRY_PATCH,
    )
    assert route_after_validation(s) == "human_review"


def test_route_after_validation_retries_when_budget_remains() -> None:
    # Confirms routing returns "patch" while state["retry_count"] < max_retries,
    # regardless of val.retry_count.
    s = _base_state()
    s["retry_count"] = 1
    s["validation_output"] = ValidationOutput(
        test_exit_code=1,
        tests_passed=False,
        lint_passed=True,
        type_check_passed=True,
        stdout="",
        stderr="fail",
        retry_count=99,  # intentionally wrong — must NOT drive routing
        routing_decision=RoutingDecision.RETRY_PATCH,
    )
    assert route_after_validation(s) == "patch"
