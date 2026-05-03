from __future__ import annotations

from evaluation.metrics import summarize_runs


def test_summarize_runs_basic() -> None:
    runs = [
        {"pr_opened": True, "tests_passed": True, "runtime_seconds": 10.0},
        {"pr_opened": False, "tests_passed": False, "runtime_seconds": 5.0},
    ]
    m = summarize_runs(runs)
    assert m["n"] == 2
    assert m["pr_success_rate"] == 50.0
