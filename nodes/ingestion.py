from __future__ import annotations

import os
import re

from github import Github

from graph.state import GraphState, IssueContext
from logging_config import get_logger

logger = get_logger(__name__)


def ingestion_node(state: GraphState) -> dict:
    """Deterministic node. No LLM. Fetches GitHub issue metadata."""
    logger.info("node starting")
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        logger.error("GITHUB_TOKEN is not set")
        return {
            "error_message": "GITHUB_TOKEN is not set",
            "final_status": "failed",
        }

    g = Github(token)
    url = state["issue_url"]

    match = re.match(r"https://github\.com/([^/]+)/([^/]+)/issues/(\d+)", url)
    if not match:
        logger.error("Invalid GitHub issue URL: %s", url)
        return {
            "error_message": f"Invalid GitHub issue URL: {url}",
            "final_status": "failed",
        }

    owner, repo_name, issue_number = match.group(1), match.group(2), int(match.group(3))

    try:
        repo = g.get_repo(f"{owner}/{repo_name}")
        issue = repo.get_issue(issue_number)
        override = (state.get("base_commit_sha_override") or "").strip()
        if override:
            base_sha = repo.get_commit(override).sha
        else:
            branch = repo.get_branch(repo.default_branch)
            base_sha = branch.commit.sha
    except Exception as exc:  # noqa: BLE001 — surface GitHub errors to state
        logger.error("GitHub API error: %s", exc)
        return {
            "error_message": f"GitHub API error: {exc}",
            "final_status": "failed",
        }

    context = IssueContext(
        issue_number=issue_number,
        title=issue.title,
        body=issue.body or "",
        labels=[label.name for label in issue.labels],
        repo_owner=owner,
        repo_name=repo_name,
        repo_url=repo.clone_url,
        default_branch=repo.default_branch,
        base_commit_sha=base_sha,
    )

    logger.info(
        "node complete",
        extra={
            "output_payload": {
                "issue_number": context.issue_number,
                "repo": f"{owner}/{repo_name}",
                "base_commit_sha": context.base_commit_sha,
            },
        },
    )
    return {
        "issue_context": context,
        "retry_count": 0,
        "max_retries": state.get("max_retries", 3),
    }
