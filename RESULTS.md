# Benchmark Results

This file records end-to-end evaluation runs of the multi-agent code repair system
against real open-source GitHub issues.

## How to run

Dry-run mode (no PR opened, prints diff + PR template):
```bash
python main.py run --issue-url '' --dry-run
```

Full mode (opens real PR):
```bash
python main.py run --issue-url ''
```

Batch benchmark:
```bash
python main.py evaluate --benchmark-file evaluation/benchmark_issues.json
```

## Recorded Runs

| Issue | Status | Tests Pass | Lint Pass | Retries | Runtime | Cost | Notes |
|---|---|---|---|---|---|---|---|
| [click#2811](https://github.com/pallets/click/issues/2811) | human_review | no | no | 3 | ~90s | see LangSmith | CLI `--dry-run`; pinned `273fb901…`; all validations failed before pytest: `git apply` error at `src/click/core.py:265` |
| [click#3277](https://github.com/pallets/click/issues/3277) | pending | - | - | - | - | - | Not run yet |
| [black#3984](https://github.com/psf/black/issues/3984) | pending | - | - | - | - | - | Not run yet |

### Run detail — click#2811 (2026-05-04)

Command:

```bash
python main.py run \
  --issue-url "https://github.com/pallets/click/issues/2811" \
  --base-sha "273fb90106726daa16e1033eca0d677de76345eb" \
  --dry-run
```

- **Final graph status:** `human_review` (retry budget exhausted; routing after last validation was `human_review`).
- **Sandbox signals:** `tests_passed=no`, `lint_passed=no`, `type_check_passed=no`, `test_exit_code=1`, `retry_count=3`.
- **Validation stderr (representative):** `error: patch failed: src/click/core.py:265` / `patch does not apply`.
- **Wall clock (ingestion start → last validation log):** ~89s (~1m 30s).
- **Cost:** not printed in CLI; copy spend from LangSmith project **`multi-agent-code-repair`** (or your `LANGCHAIN_PROJECT`) for this thread.

## Metrics Summary (after runs complete)

- **PR success rate:** 0/1 recorded dry-runs that reached PR (none); 2 issues not yet run.
- **Test pass rate:** 0/1 (apply failed before a green pytest run on this recorded attempt).
- **Median runtime:** TBD (need ≥2 completed wall-clock samples).
- **Median cost per patch:** TBD (pull from LangSmith per run).
- **Human edit frequency:** 0/1 (no manual patch edits during the run; ended in `human_review`).

_Update this table after each `python main.py evaluate` run._
