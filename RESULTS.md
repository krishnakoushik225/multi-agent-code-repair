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

| Issue | Status | Tests Pass | Lint Pass | Type Pass | Retries | Runtime | Cost | Notes |
|---|---|---|---|---|---|---|---|---|
| [click#3277](https://github.com/pallets/click/issues/3277) | success ✅ | 1,436 passed | ✅ | ✅ | 0 | ~1m 50s | ~$0.35 | Dry-run; sandbox excludes flaky pager test (`docker/entrypoint.sh`); see [`README.md`](README.md) demo screenshots |
| [click#2811](https://github.com/pallets/click/issues/2811) | human_review | ❌ | ❌ | ❌ | 3 | 1m 55s | ~$0.40 | Patch did not apply at pinned SHA; retries exhausted → human_review (see run detail below) |
| [black#3984](https://github.com/psf/black/issues/3984) | pending | - | - | - | - | - | - | Not run yet |

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

## Metrics Summary

- **PR success rate:** 0% (dry-run mode; no PRs opened — by design)
- **click#3277 (2026-05-09):** **1,436** tests passed in sandbox; lint (Ruff) and type-check (Mypy) clean; **0 retries**; ~1m 50s wall clock; ~$0.35 spend (see Recorded Runs)
- **Lint / type pass rate:** 100% on recorded successful validation run
- **Median runtime / cost (historical mixed runs):** ~2 minutes per issue; ~$0.37 median cost where logged

_Update this table after each `python main.py evaluate` run._
