from __future__ import annotations

from rich.console import Console

from graph.state import (
    GraphState,
    IssueContext,
    PatchOutput,
    PlanningOutput,
    ValidationOutput,
    as_model,
)
from tools.github_tools import ensure_branch_name, slugify
from tools.pr_template import build_pr_body, build_pr_title

console = Console()


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

    console.print("\n========== DRY RUN — file changes ==========\n")
    for fc in patch.file_changes:
        console.print(f"\n[bold]File:[/bold] {fc.path}")
        console.print(f"[bold]Change:[/bold] {fc.description}")
        console.print(f"[dim]Search:[/dim]\n{fc.search[:200]}")
        console.print(f"[dim]Replace:[/dim]\n{fc.replace[:200]}")
    console.print("\n========== DRY RUN — PR title ==========\n")
    console.print(title)
    console.print("\n========== DRY RUN — branch ==========\n")
    console.print(branch_name)
    console.print("\n========== DRY RUN — PR body template ==========\n")
    console.print(body)

    return {"final_status": "success"}
