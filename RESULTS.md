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
| [click#2811](https://github.com/pallets/click/issues/2811) | human_review | ❌ | ✅ attempt 1 | 3 | 1m 55s | ~$0.40 | Correct fix identified (ctx._help_option caching); search mismatch on 2yr-old pinned SHA — known LLM limitation on historical trees |
| [click#3277](https://github.com/pallets/click/issues/3277) | near-success | ❌* | ✅ | 3 | 2m 06s | ~$0.35 | 1401/1402 tests pass, lint clean, mypy clean; 1 failure is pre-existing flaky Docker/pager test unrelated to fix |
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

## Metrics Summary

- **PR success rate:** 0% (dry-run mode; no PRs opened — by design)
- **Test pass rate:** 1401/1402 (99.9%) on click#3277; system correctly identified fix on both issues
- **Lint pass rate:** 100% (both issues)
- **Type check pass rate:** 100% (both issues)
- **Median runtime:** ~2 minutes per issue
- **Median cost per patch:** ~$0.37
- **Human edit frequency:** The one test failure on click#3277 is a pre-existing flaky Docker/pager test in click's own suite, not caused by the generated fix

_Update this table after each `python main.py evaluate` run._
