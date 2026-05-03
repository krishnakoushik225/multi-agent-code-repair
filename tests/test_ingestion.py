from __future__ import annotations

from unittest.mock import MagicMock, patch

from graph.state import GraphState
from nodes.ingestion import ingestion_node


def test_ingestion_invalid_url() -> None:
    state: GraphState = {
        "issue_url": "https://example.com/not-github",
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
    out = ingestion_node(state)
    assert out["final_status"] == "failed"
    assert out.get("error_message")


@patch.dict("os.environ", {"GITHUB_TOKEN": "token"})
@patch("nodes.ingestion.Github")
def test_ingestion_happy_path(mock_github: MagicMock) -> None:
    mock_issue = MagicMock()
    mock_issue.title = "Bug"
    mock_issue.body = "Details"
    mock_issue.labels = []

    mock_repo = MagicMock()
    mock_repo.get_issue.return_value = mock_issue
    mock_repo.clone_url = "https://github.com/o/r.git"
    mock_repo.default_branch = "main"
    mock_repo.get_branch.return_value.commit.sha = "abc123deadbeef"

    mock_github.return_value.get_repo.return_value = mock_repo

    state: GraphState = {
        "issue_url": "https://github.com/o/r/issues/7",
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
    out = ingestion_node(state)
    assert out["retry_count"] == 0
    assert out["issue_context"] is not None
    assert out["issue_context"].issue_number == 7
    assert out["issue_context"].base_commit_sha == "abc123deadbeef"


@patch.dict("os.environ", {"GITHUB_TOKEN": "token"})
@patch("nodes.ingestion.Github")
def test_ingestion_base_sha_override(mock_github: MagicMock) -> None:
    mock_issue = MagicMock()
    mock_issue.title = "T"
    mock_issue.body = ""
    mock_issue.labels = []

    mock_commit = MagicMock()
    mock_commit.sha = "273fb90106726daa16e1033eca0d677de76345eb"

    mock_repo = MagicMock()
    mock_repo.get_issue.return_value = mock_issue
    mock_repo.clone_url = "https://github.com/o/r.git"
    mock_repo.default_branch = "main"
    mock_repo.get_commit.return_value = mock_commit

    mock_github.return_value.get_repo.return_value = mock_repo

    pin = "273fb90106726daa16e1033eca0d677de76345eb"
    state: GraphState = {
        "issue_url": "https://github.com/o/r/issues/1",
        "dry_run": False,
        "base_commit_sha_override": pin,
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
    out = ingestion_node(state)
    mock_repo.get_branch.assert_not_called()
    assert out["issue_context"].base_commit_sha == pin
