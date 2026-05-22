from __future__ import annotations

from unittest.mock import MagicMock, patch

from graph.state import (
    FileChange,
    GraphState,
    IssueContext,
    PatchOutput,
    RoutingDecision,
)
from nodes.validation_node import validation_node


def _make_state(file_changes: list[FileChange], retry_count: int = 0) -> GraphState:
    return {
        "issue_url": "https://github.com/o/r/issues/1",
        "dry_run": False,
        "base_commit_sha_override": None,
        "issue_context": IssueContext(
            issue_number=1,
            title="T",
            body="B",
            labels=[],
            repo_owner="o",
            repo_name="r",
            repo_url="https://github.com/o/r.git",
            default_branch="main",
            base_commit_sha="abc123",
        ),
        "research_output": None,
        "planning_output": None,
        "patch_output": PatchOutput(
            file_changes=file_changes,
            explanation="test",
            tests_written=None,
        ),
        "validation_output": None,
        "pr_output": None,
        "retry_count": retry_count,
        "max_retries": 3,
        "error_message": None,
        "final_status": None,
    }


@patch("nodes.validation_node.apply_patch_and_run_tests")
def test_sanity_check_empty_changes_skips_docker(mock_sandbox: MagicMock) -> None:
    state = _make_state(file_changes=[])
    out = validation_node(state)
    mock_sandbox.assert_not_called()
    val = out["validation_output"]
    assert not val.tests_passed
    assert "empty" in val.stderr.lower()
    assert val.routing_decision == RoutingDecision.RETRY_PATCH


@patch("nodes.validation_node.apply_patch_and_run_tests")
def test_sanity_check_empty_search_skips_docker(mock_sandbox: MagicMock) -> None:
    changes = [FileChange(path="src/x.py", search="   ", replace="b", description="d")]
    state = _make_state(file_changes=changes)
    out = validation_node(state)
    mock_sandbox.assert_not_called()
    val = out["validation_output"]
    assert not val.tests_passed
    assert "search string is empty" in val.stderr


@patch("nodes.validation_node.apply_patch_and_run_tests")
def test_sanity_check_identical_search_replace_skips_docker(mock_sandbox: MagicMock) -> None:
    changes = [FileChange(path="src/x.py", search="a", replace="a", description="d")]
    state = _make_state(file_changes=changes)
    out = validation_node(state)
    mock_sandbox.assert_not_called()
    assert "identical" in out["validation_output"].stderr


@patch("nodes.validation_node.apply_patch_and_run_tests")
def test_sanity_check_routes_human_review_when_retries_exhausted(mock_sandbox: MagicMock) -> None:
    changes = [FileChange(path="src/x.py", search="", replace="b", description="d")]
    state = _make_state(file_changes=changes, retry_count=3)
    out = validation_node(state)
    mock_sandbox.assert_not_called()
    assert out["validation_output"].routing_decision == RoutingDecision.HUMAN_REVIEW


@patch("nodes.validation_node.apply_patch_and_run_tests")
def test_valid_changes_call_docker(mock_sandbox: MagicMock) -> None:
    mock_sandbox.return_value = {
        "test_exit_code": 0,
        "lint_exit_code": 0,
        "type_check_exit_code": 0,
        "stdout": "TEST_EXIT=0\nLINT_EXIT=0\nTYPE_EXIT=0\n",
        "stderr": "",
    }
    changes = [FileChange(path="src/x.py", search="old", replace="new", description="d")]
    state = _make_state(file_changes=changes)
    out = validation_node(state)
    mock_sandbox.assert_called_once()
    assert out["validation_output"].tests_passed
