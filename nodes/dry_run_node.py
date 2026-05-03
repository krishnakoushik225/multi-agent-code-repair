from __future__ import annotations

import sys

from graph.state import GraphState, IssueContext, PatchOutput, PlanningOutput, ValidationOutput, as_model
from tools.github_tools import ensure_branch_name, slugify
from tools.pr_template import build_pr_body, build_pr_title


def dry_run_node(state: GraphState) -> dict:
    """
    Skip opening a PR: print unified diff and PR body template to stdout, then end.
    """
    raw_ctx = state["issue_context"]
    raw_patch = state["patch_output"]
    raw_planning = state["planning_output"]
    raw_validation = state["validation_output"]
    if raw_ctx is None or raw_patch is None or raw_planning is None or raw_validation is None:
        return {"error_message": "Missing context for dry run output", "final_status": "failed"}

    ctx = as_model(IssueContext, raw_ctx)
    patch = as_model(PatchOutput, raw_patch)
    planning = as_model(PlanningOutput, raw_planning)
    validation = as_model(ValidationOutput, raw_validation)

    branch_name = f"{ensure_branch_name(ctx.issue_number)}-{slugify(ctx.title)}"
    title = build_pr_title(ctx)
    body = build_pr_body(ctx, planning, patch, validation)

    print("\n========== DRY RUN — unified diff ==========\n", file=sys.stdout)
    print(patch.unified_diff or "(empty diff)", file=sys.stdout)
    print("\n========== DRY RUN — PR title ==========\n", file=sys.stdout)
    print(title, file=sys.stdout)
    print("\n========== DRY RUN — branch ==========\n", file=sys.stdout)
    print(branch_name, file=sys.stdout)
    print("\n========== DRY RUN — PR body template ==========\n", file=sys.stdout)
    print(body, file=sys.stdout)

    return {"final_status": "success"}
