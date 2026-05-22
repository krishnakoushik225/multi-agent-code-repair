from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from graph.state import (
    GraphState,
    IssueContext,
    PatchOutput,
    PlanningOutput,
    ValidationOutput,
    as_model,
)
from logging_config import get_logger

logger = get_logger(__name__)
_console = Console(stderr=True)


def human_review_node(state: GraphState) -> dict:
    """Terminal node: emit actionable Rich summary so a human knows exactly what to review."""
    logger.info("node starting — escalating to human review")

    error_msg = state.get("error_message") or "No error message recorded"
    retry_count = int(state.get("retry_count", 0))
    max_retries = int(state.get("max_retries", 3))

    raw_ctx = state.get("issue_context")
    raw_planning = state.get("planning_output")
    raw_patch = state.get("patch_output")
    raw_validation = state.get("validation_output")

    ctx = as_model(IssueContext, raw_ctx) if raw_ctx is not None else None
    planning = as_model(PlanningOutput, raw_planning) if raw_planning is not None else None
    patch = as_model(PatchOutput, raw_patch) if raw_patch is not None else None
    validation = as_model(ValidationOutput, raw_validation) if raw_validation is not None else None

    _console.print()
    _console.rule("[bold red]Human Review Required[/bold red]")

    if ctx is not None:
        _console.print(
            Panel(
                f"[bold]{ctx.repo_owner}/{ctx.repo_name}[/bold] — Issue #{ctx.issue_number}\n"
                f"[italic]{ctx.title}[/italic]\n\n"
                f"[dim]Base commit:[/dim] {ctx.base_commit_sha or 'default branch'}",
                title="Issue",
                border_style="yellow",
            )
        )

    # Escalation reason
    _console.print(
        Panel(
            f"[red]{error_msg}[/red]\n\nRetries: {retry_count} / {max_retries}",
            title="Escalation Reason",
            border_style="red",
        )
    )

    # Validation results table
    if validation is not None:
        tbl = Table(title="Last Validation Run", show_header=True, header_style="bold cyan")
        tbl.add_column("Check")
        tbl.add_column("Result")
        tbl.add_row(
            "Tests", "[green]PASS[/green]" if validation.tests_passed else "[red]FAIL[/red]"
        )
        tbl.add_row("Lint", "[green]PASS[/green]" if validation.lint_passed else "[red]FAIL[/red]")
        tbl.add_row(
            "Type check",
            "[green]PASS[/green]" if validation.type_check_passed else "[red]FAIL[/red]",
        )
        _console.print(tbl)
        if validation.stderr.strip():
            _console.print(
                Panel(
                    validation.stderr[:2000],
                    title="Stderr (last 2000 chars)",
                    border_style="red",
                )
            )

    # Patch file changes
    if patch is not None and patch.file_changes:
        tbl2 = Table(title="Proposed File Changes", show_header=True, header_style="bold magenta")
        tbl2.add_column("File", style="cyan")
        tbl2.add_column("Description")
        for fc in patch.file_changes:
            tbl2.add_row(fc.path, fc.description)
        _console.print(tbl2)
        if patch.explanation:
            _console.print(
                Panel(patch.explanation, title="Patch Explanation", border_style="magenta")
            )

    # Fix strategy
    if planning is not None:
        _console.print(
            Panel(
                f"[bold]Strategy:[/bold] {planning.fix_strategy}\n"
                f"[bold]Risk level:[/bold] {planning.risk_level.value}\n"
                f"[bold]Ambiguous:[/bold] {planning.ambiguous}"
                + (
                    f"\n[bold]Reason:[/bold] {planning.ambiguity_reason}"
                    if planning.ambiguity_reason
                    else ""
                ),
                title="Planned Fix",
                border_style="yellow",
            )
        )

    _console.rule("[dim]Action Required[/dim]")
    _console.print(
        "[bold]Next steps:[/bold]\n"
        "  1. Review the proposed file changes and patch explanation above.\n"
        "  2. Apply manually or open a draft PR from the patch output.\n"
        "  3. Re-run with a narrower issue scope or adjusted max-retries if needed.\n"
    )

    logger.info(
        "node complete",
        extra={
            "output_payload": {
                "retry_count": retry_count,
                "has_patch": patch is not None,
                "error_message": error_msg[:120],
            }
        },
    )
    return {"final_status": "human_review"}
