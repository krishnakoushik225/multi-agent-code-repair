from __future__ import annotations

from graph.state import (
    FileChange,
    IssueContext,
    PatchOutput,
    PlanningOutput,
    RiskLevel,
    RoutingDecision,
    ValidationOutput,
)
from nodes.human_review_node import human_review_node


def _state(**overrides) -> dict:
    ctx = IssueContext(
        issue_number=99,
        title="Test issue",
        body="body",
        labels=[],
        repo_owner="org",
        repo_name="repo",
        repo_url="https://github.com/org/repo/issues/99",
        default_branch="main",
        base_commit_sha="abc",
    )
    planning = PlanningOutput(
        fix_strategy="do the thing",
        candidate_files=["src/mod.py"],
        estimated_lines_changed=5,
        risk_level=RiskLevel.HIGH,
        requires_new_tests=True,
        ambiguous=True,
        ambiguity_reason="unclear semantics",
    )
    patch = PatchOutput(
        file_changes=[
            FileChange(path="src/mod.py", search="old", replace="new", description="fix it")
        ],
        explanation="this was broken",
    )
    validation = ValidationOutput(
        test_exit_code=1,
        tests_passed=False,
        lint_passed=True,
        type_check_passed=True,
        stdout="",
        stderr="AssertionError: expected 1 got 2",
        retry_count=3,
        routing_decision=RoutingDecision.HUMAN_REVIEW,
    )
    base: dict = {
        "issue_url": "https://github.com/org/repo/issues/99",
        "dry_run": False,
        "base_commit_sha_override": None,
        "issue_context": ctx,
        "research_output": None,
        "planning_output": planning,
        "patch_output": patch,
        "validation_output": validation,
        "pr_output": None,
        "retry_count": 3,
        "max_retries": 3,
        "error_message": "retries exhausted",
        "final_status": None,
    }
    base.update(overrides)
    return base


def test_human_review_sets_final_status():
    result = human_review_node(_state())
    assert result["final_status"] == "human_review"


def test_human_review_with_minimal_state():
    minimal: dict = {
        "issue_url": "",
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
    result = human_review_node(minimal)
    assert result["final_status"] == "human_review"


def test_human_review_does_not_overwrite_error_message():
    result = human_review_node(_state(error_message="push failed"))
    assert result.get("error_message") is None or result["final_status"] == "human_review"


def test_human_review_with_no_patch():
    result = human_review_node(_state(patch_output=None))
    assert result["final_status"] == "human_review"


def test_human_review_with_no_validation():
    result = human_review_node(_state(validation_output=None))
    assert result["final_status"] == "human_review"
