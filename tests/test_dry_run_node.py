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
from nodes.dry_run_node import dry_run_node


def _full_state(**overrides) -> dict:
    ctx = IssueContext(
        issue_number=7,
        title="Dry run title",
        body="body",
        labels=[],
        repo_owner="org",
        repo_name="repo",
        repo_url="https://github.com/org/repo/issues/7",
        default_branch="main",
        base_commit_sha="deadbeef",
    )
    planning = PlanningOutput(
        fix_strategy="no-op",
        candidate_files=["a.py"],
        estimated_lines_changed=1,
        risk_level=RiskLevel.LOW,
        requires_new_tests=False,
        ambiguous=False,
    )
    patch = PatchOutput(
        file_changes=[FileChange(path="a.py", search="old", replace="new", description="rename")],
        explanation="test explanation",
    )
    validation = ValidationOutput(
        test_exit_code=0,
        tests_passed=True,
        lint_passed=True,
        type_check_passed=True,
        stdout="",
        stderr="",
        retry_count=0,
        routing_decision=RoutingDecision.COMPLETE,
    )
    state = {
        "issue_url": "https://github.com/org/repo/issues/7",
        "dry_run": True,
        "base_commit_sha_override": None,
        "issue_context": ctx,
        "research_output": None,
        "planning_output": planning,
        "patch_output": patch,
        "validation_output": validation,
        "pr_output": None,
        "retry_count": 0,
        "max_retries": 3,
        "error_message": None,
        "final_status": None,
    }
    state.update(overrides)
    return state


def test_dry_run_returns_success():
    result = dry_run_node(_full_state())
    assert result["final_status"] == "success"


def test_dry_run_missing_patch_returns_failed():
    result = dry_run_node(_full_state(patch_output=None))
    assert result["final_status"] == "failed"
    assert result["error_message"]


def test_dry_run_missing_context_returns_failed():
    result = dry_run_node(_full_state(issue_context=None))
    assert result["final_status"] == "failed"


def test_dry_run_does_not_set_pr_output():
    result = dry_run_node(_full_state())
    assert "pr_output" not in result
