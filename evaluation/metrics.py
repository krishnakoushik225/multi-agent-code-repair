from __future__ import annotations

from statistics import median
from typing import Any


def summarize_runs(runs: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Compute aggregate metrics from benchmark run records.

    Each run dict should include keys like: issue_url, final_status, pr_opened,
    tests_passed, human_edits (optional), runtime_seconds (optional), cost_usd (optional).
    """
    if not runs:
        return {
            "pr_success_rate": 0.0,
            "test_pass_rate": 0.0,
            "human_edit_frequency": None,
            "median_runtime_seconds": None,
            "cost_per_patch_usd": None,
            "n": 0,
        }

    pr_opened = sum(1 for r in runs if r.get("pr_opened"))
    pr_success_rate = pr_opened / len(runs)
    pr_runs = [r for r in runs if r.get("pr_opened")]
    tests_ok = sum(1 for r in pr_runs if r.get("tests_passed"))
    test_pass_rate = tests_ok / max(1, len(pr_runs))

    edits = [r.get("human_edits") for r in runs if r.get("human_edits") is not None]
    human_edit_frequency = sum(1 for e in edits if e) / len(edits) if edits else None

    runtimes = [float(r["runtime_seconds"]) for r in runs if r.get("runtime_seconds") is not None]
    costs = [float(r["cost_usd"]) for r in runs if r.get("cost_usd") is not None]

    return {
        "pr_success_rate": round(pr_success_rate * 100, 2),
        "test_pass_rate": round(test_pass_rate * 100, 2),
        "human_edit_frequency": round(human_edit_frequency * 100, 2) if human_edit_frequency is not None else None,
        "median_runtime_seconds": median(runtimes) if runtimes else None,
        "cost_per_patch_usd": median(costs) if costs else None,
        "n": len(runs),
    }
