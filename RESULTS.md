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
| [click#2811](https://github.com/pallets/click/issues/2811) | pending | - | - | - | - | - | Awaiting run with credentials |
| [click#3277](https://github.com/pallets/click/issues/3277) | pending | - | - | - | - | - | Awaiting run with credentials |
| [black#3984](https://github.com/psf/black/issues/3984) | pending | - | - | - | - | - | Awaiting run with credentials |

## Metrics Summary (after runs complete)

- **PR success rate:** TBD
- **Test pass rate:** TBD
- **Median runtime:** TBD
- **Median cost per patch:** TBD
- **Human edit frequency:** TBD

_Update this table after each `python main.py evaluate` run._
