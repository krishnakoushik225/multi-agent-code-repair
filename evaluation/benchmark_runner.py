from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

from rich.console import Console
from rich.table import Table

from evaluation.metrics import summarize_runs
from graph.graph_builder import build_graph

console = Console()


def run_benchmark(benchmark_file: str) -> None:
    path = Path(benchmark_file)
    issues: list[dict[str, Any]] = json.loads(path.read_text(encoding="utf-8"))

    graph = build_graph()
    runs: list[dict[str, Any]] = []

    for item in issues:
        issue_url = str(item["issue_url"])
        t0 = time.time()
        pin = item.get("base_commit_sha")
        pin_str = None if pin in (None, "") else str(pin).strip()
        initial_state = {
            "issue_url": issue_url,
            "dry_run": False,
            "base_commit_sha_override": pin_str or None,
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
        tid = f"bench-{issue_url.replace('/', '_')}"
        if pin_str:
            tid = f"{tid}_{pin_str[:16]}"
        config = {"configurable": {"thread_id": tid}}
        console.print(f"\n[bold cyan]Running:[/bold cyan] {issue_url}")
        for event in graph.stream(initial_state, config=config):
            for node_name in event:
                console.print(f"  [dim]✓ {node_name}[/dim]")
        snap = graph.get_state(config)
        final_state = snap.values

        pr = final_state.get("pr_output")
        pr_opened = bool(
            pr
            and getattr(pr, "success", False)
            and pr.pr_url
            and not str(pr.pr_url).startswith("dry-run:")
        )
        val = final_state.get("validation_output")
        tests_passed = bool(val and getattr(val, "tests_passed", False))

        runs.append(
            {
                "issue_url": issue_url,
                "final_status": final_state.get("final_status"),
                "pr_opened": pr_opened,
                "tests_passed": tests_passed,
                "runtime_seconds": time.time() - t0,
                "human_edits": item.get("human_edits_required"),
                "cost_usd": item.get("cost_usd"),
            },
        )

    metrics = summarize_runs(runs)
    table = Table(title="Benchmark Summary")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", style="white")
    for k, v in metrics.items():
        table.add_row(k, str(v))
    console.print(table)
