from __future__ import annotations

import os

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table

from graph.graph_builder import build_graph

load_dotenv()

app = typer.Typer()
console = Console()


@app.command()
def run(
    issue_url: str = typer.Option(..., help="Full GitHub issue URL"),
    max_retries: int = typer.Option(3, help="Max patch retry attempts"),
    model: str = typer.Option("gpt-4o", help="LLM model via LiteLLM (default for all agents)"),
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="After validation passes, skip opening a PR and print diff + PR template to stdout",
    ),
    base_sha: str | None = typer.Option(
        None,
        "--base-sha",
        help="Pin research/validation to this commit (full SHA). Use for historical bugs already fixed on main.",
    ),
):
    """Run the multi-agent code repair system on a GitHub issue."""
    os.environ["LLM_MODEL"] = model

    graph = build_graph()

    override = base_sha.strip() if base_sha else None
    initial_state = {
        "issue_url": issue_url,
        "dry_run": dry_run,
        "base_commit_sha_override": override,
        "issue_context": None,
        "research_output": None,
        "planning_output": None,
        "patch_output": None,
        "validation_output": None,
        "pr_output": None,
        "retry_count": 0,
        "max_retries": max_retries,
        "error_message": None,
        "final_status": None,
    }

    console.print(
        f"\n[bold cyan]Starting multi-agent code repair for:[/bold cyan] {issue_url}\n",
    )

    thread_id = issue_url.replace("/", "_")
    if override:
        thread_id = f"{thread_id}_{override[:16]}"
    config = {"configurable": {"thread_id": thread_id}}

    for event in graph.stream(initial_state, config=config):
        for node_name, _node_output in event.items():
            console.print(f"[green]✓[/green] Completed node: [bold]{node_name}[/bold]")

    snap = graph.get_state(config)
    final_state = snap.values

    patch = final_state.get("patch_output")
    validation = final_state.get("validation_output")

    if patch is not None:
        console.print("\n[bold yellow]Last Unified Diff[/bold yellow]")
        console.print(patch.unified_diff)

    if validation is not None:
        console.print("\n[bold yellow]Validation Summary[/bold yellow]")
        console.print(f"tests_passed: {validation.tests_passed}")
        console.print(f"lint_passed: {validation.lint_passed}")
        console.print(f"type_check_passed: {validation.type_check_passed}")
        console.print(f"test_exit_code: {validation.test_exit_code}")
        console.print(f"retry_count: {validation.retry_count}")

        if validation.stdout:
            console.print("\n[bold yellow]Validation STDOUT[/bold yellow]")
            console.print(validation.stdout)

        if validation.stderr:
            console.print("\n[bold yellow]Validation STDERR[/bold yellow]")
            console.print(validation.stderr)

    table = Table(title="Run Summary")
    table.add_column("Field", style="cyan")
    table.add_column("Value", style="white")
    table.add_row("Status", str(final_state.get("final_status", "unknown")))
    table.add_row("Retries Used", str(final_state.get("retry_count", 0)))
    if final_state.get("error_message"):
        table.add_row("Error", str(final_state["error_message"]))
    pr = final_state.get("pr_output")
    if pr is not None:
        table.add_row("PR URL", str(pr.pr_url))
    console.print(table)


@app.command()
def evaluate(
    benchmark_file: str = typer.Option("evaluation/benchmark_issues.json"),
):
    """Run system on benchmark issue set and compute metrics."""
    from evaluation.benchmark_runner import run_benchmark

    run_benchmark(benchmark_file)


if __name__ == "__main__":
    app()
