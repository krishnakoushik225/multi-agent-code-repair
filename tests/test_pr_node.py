from __future__ import annotations

from unittest.mock import MagicMock, patch

from graph.state import (
    FileChange,
    GraphState,
    IssueContext,
    PatchOutput,
    PlanningOutput,
    PROutput,
    RiskLevel,
    RoutingDecision,
    ValidationOutput,
)
from nodes.pr_node import pr_node


def _base_state() -> GraphState:
    return {
        "issue_url": "https://github.com/o/r/issues/1",
        "dry_run": False,
        "base_commit_sha_override": None,
        "issue_context": IssueContext(
            issue_number=1,
            title="Bug title",
            body="Body",
            labels=[],
            repo_owner="o",
            repo_name="r",
            repo_url="https://github.com/o/r.git",
            default_branch="main",
            base_commit_sha="abc123",
        ),
        "research_output": None,
        "planning_output": PlanningOutput(
            fix_strategy="Apply minimal patch.",
            candidate_files=["src/x.py"],
            estimated_lines_changed=3,
            risk_level=RiskLevel.LOW,
            requires_new_tests=False,
            ambiguous=False,
        ),
        "patch_output": PatchOutput(
            file_changes=[
                FileChange(path="src/x.py", search="old", replace="new", description="fix it")
            ],
            explanation="Fixes the bug.",
            tests_written=None,
        ),
        "validation_output": ValidationOutput(
            test_exit_code=0,
            tests_passed=True,
            lint_passed=True,
            type_check_passed=True,
            stdout="",
            stderr="",
            retry_count=0,
            routing_decision=RoutingDecision.CONTINUE,
        ),
        "pr_output": None,
        "retry_count": 0,
        "max_retries": 3,
        "error_message": None,
        "final_status": None,
    }


def test_pr_node_missing_context_returns_failed() -> None:
    state = _base_state()
    state["patch_output"] = None
    out = pr_node(state)
    assert out["final_status"] == "failed"
    assert out.get("error_message")


@patch.dict("os.environ", {}, clear=True)
def test_pr_node_missing_token_returns_failed() -> None:
    out = pr_node(_base_state())
    assert out["final_status"] == "failed"
    assert "GITHUB_TOKEN" in out["error_message"]


@patch.dict("os.environ", {"GITHUB_TOKEN": "tok"})
@patch("nodes.pr_node.git_push_patch_branch")
@patch("nodes.pr_node.Github")
def test_pr_node_push_failure_escalates_to_human_review(
    mock_github: MagicMock,
    mock_push: MagicMock,
) -> None:
    mock_github.return_value.get_repo.return_value = MagicMock()
    mock_push.side_effect = RuntimeError("git push failed: permission denied")

    out = pr_node(_base_state())

    assert out["final_status"] == "human_review", (
        "A post-validation push failure must escalate to human_review so the validated patch is not lost"
    )
    assert "Failed to push branch" in out["error_message"]


@patch.dict("os.environ", {"GITHUB_TOKEN": "tok"})
@patch("nodes.pr_node.git_push_patch_branch")
@patch("nodes.pr_node.Github")
def test_pr_node_create_pull_failure_escalates_to_human_review(
    mock_github: MagicMock,
    mock_push: MagicMock,
) -> None:
    mock_push.return_value = None
    mock_repo = MagicMock()
    mock_repo.create_pull.side_effect = Exception("422 Unprocessable Entity — PR already exists")
    mock_github.return_value.get_repo.return_value = mock_repo

    out = pr_node(_base_state())

    assert out["final_status"] == "human_review", (
        "A post-push PR creation failure must escalate to human_review so the branch can be used"
    )
    assert "Failed to create pull request" in out["error_message"]


@patch.dict("os.environ", {"GITHUB_TOKEN": "tok"})
@patch("nodes.pr_node.git_push_patch_branch")
@patch("nodes.pr_node.Github")
def test_pr_node_happy_path(
    mock_github: MagicMock,
    mock_push: MagicMock,
) -> None:
    mock_push.return_value = None
    mock_pr = MagicMock()
    mock_pr.html_url = "https://github.com/o/r/pull/42"
    mock_pr.number = 42
    mock_pr.title = "fix: auto-repair for issue #1 — Bug title"
    mock_repo = MagicMock()
    mock_repo.create_pull.return_value = mock_pr
    mock_github.return_value.get_repo.return_value = mock_repo

    out = pr_node(_base_state())

    assert out["final_status"] == "success"
    assert isinstance(out["pr_output"], PROutput)
    assert out["pr_output"].pr_url == "https://github.com/o/r/pull/42"
    assert out["pr_output"].pr_number == 42
    assert out["pr_output"].success is True
