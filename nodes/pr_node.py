from __future__ import annotations

import os

from github import Github

from graph.state import (
    GraphState,
    IssueContext,
    PatchOutput,
    PlanningOutput,
    PROutput,
    ValidationOutput,
    as_model,
)
from logging_config import get_logger
from tools.github_tools import ensure_branch_name, git_push_patch_branch, slugify
from tools.pr_template import build_pr_body, build_pr_title

logger = get_logger(__name__)


def pr_node(state: GraphState) -> dict:
    """Deterministic node. Opens a GitHub PR with the validated patch."""
    logger.info("node starting")
    raw_ctx = state["issue_context"]
    raw_patch = state["patch_output"]
    raw_planning = state["planning_output"]
    raw_validation = state["validation_output"]
    if raw_ctx is None or raw_patch is None or raw_planning is None or raw_validation is None:
        logger.error("Missing context for PR creation")
        return {"error_message": "Missing context for PR creation", "final_status": "failed"}

    ctx = as_model(IssueContext, raw_ctx)
    patch = as_model(PatchOutput, raw_patch)
    planning = as_model(PlanningOutput, raw_planning)
    validation = as_model(ValidationOutput, raw_validation)

    title = build_pr_title(ctx)
    pr_body = build_pr_body(ctx, planning, patch, validation)
    branch_name = f"{ensure_branch_name(ctx.issue_number)}-{slugify(ctx.title)}"

    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        logger.error("GITHUB_TOKEN is not set")
        return {"error_message": "GITHUB_TOKEN is not set", "final_status": "failed"}

    g = Github(token)
    try:
        repo = g.get_repo(f"{ctx.repo_owner}/{ctx.repo_name}")
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to fetch repo: %s", exc)
        return {
            "error_message": f"Failed to fetch repo: {exc}",
            "final_status": "failed",
        }

    commit_message = f"fix: issue #{ctx.issue_number} — {ctx.title}"

    try:
        git_push_patch_branch(
            repo_owner=ctx.repo_owner,
            repo_name=ctx.repo_name,
            default_branch=ctx.default_branch,
            branch_name=branch_name,
            file_changes=[fc.model_dump() for fc in patch.file_changes],
            commit_message=commit_message,
            base_commit_sha=ctx.base_commit_sha or None,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to push branch: %s", exc)
        return {
            "error_message": f"Failed to push branch: {exc}",
            "final_status": "failed",
        }

    try:
        pr = repo.create_pull(
            title=title,
            body=pr_body,
            head=branch_name,
            base=ctx.default_branch,
        )
    except Exception as exc:  # noqa: BLE001
        logger.error("Failed to create pull request: %s", exc)
        return {
            "error_message": f"Failed to create pull request: {exc}",
            "final_status": "failed",
        }

    output = PROutput(
        pr_url=pr.html_url,
        pr_number=int(pr.number),
        title=pr.title,
        success=True,
    )
    logger.info(
        "node complete",
        extra={
            "output_payload": {
                "pr_url": output.pr_url,
                "pr_number": output.pr_number,
                "branch_name": branch_name,
            },
        },
    )
    return {"pr_output": output, "final_status": "success"}
