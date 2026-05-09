![CI](https://github.com/krishnakoushik225/multi-agent-code-repair/actions/workflows/ci.yml/badge.svg)

# Multi-agent autonomous code repair

**On a real [pallets/click](https://github.com/pallets/click) issue, validation saw 1,401 / 1,402 tests passing with Ruff and Mypy clean—median wall-clock on the order of ~2 minutes and ~$0.37 model spend per end-to-end attempt** (see [`RESULTS.md`](RESULTS.md)). The remaining failure is a known flaky Docker/pager test in upstream Click’s suite, not introduced by the generated fix.

This repository implements a **stateful LangGraph workflow**, not a prompt chain: it ingests a GitHub issue, researches the repo with **deterministic tools plus LLM reasoning**, plans a minimal change, emits **structured search-and-replace edits** grounded in **verbatim files at a pinned commit**, validates in a **resource-limited Docker sandbox** (pytest, Ruff, Mypy), **retries with structured failure feedback**, optionally opens a PR, and persists progress with **SQLite checkpointing** so runs can resume after interruptions.

If you only read one architectural lesson: **unified diffs often fail on pinned historical SHAs because models invent context lines.** This system sidesteps that class of failure by fetching real file contents at `base_commit_sha` and asking the model for explicit `search`/`replace` blocks—design driven by production failures, not a tutorial default.

---

## Table of contents

- [Why this stands out](#why-this-stands-out-in-a-crowded-ai-portfolio)
- [Demonstrated outcomes](#demonstrated-outcomes)
- [Architecture](#architecture-at-a-glance)
- [Quickstart](#quickstart)
- [Technical decisions](#technical-decisions)
- [Repository layout](#repository-layout)
- [Contributing & operator docs](#contributing--operator-docs)

---

## Why this stands out (in a crowded AI portfolio)

| Signal | What this repo does |
|--------|----------------------|
| **Real integrations** | GitHub API (PyGithub), Docker SDK, LiteLLM—not mocked demos |
| **Measured on real OSS** | Benchmarks recorded against live issues; metrics in [`RESULTS.md`](RESULTS.md) |
| **Stateful orchestration** | Conditional edges over typed graph state, not a single mega-prompt |
| **Safety boundaries** | Sandboxed execution with network isolation and CPU/memory caps |
| **Operability** | SQLite checkpoints, structured logging with correlation IDs (`logging_config.py`), CI (Ruff + pytest) |
| **Honest iteration** | Patch representation evolved from fragile unified-diff apply to pinned-SHA search/replace after observing real apply failures |

---

## Demonstrated outcomes

Recorded runs (commands and stderr excerpts) live in **[`RESULTS.md`](RESULTS.md)**. Summary:

| Issue | Outcome | Notes |
|-------|---------|--------|
| [click#3277](https://github.com/pallets/click/issues/3277) | **Near-success:** 1,401 / 1,402 tests; lint & type-check clean | Single failure attributed to upstream flaky test |
| [click#2811](https://github.com/pallets/click/issues/2811) | Routed to **human review** after retries | Illustrates limits when the tree at a pinned SHA diverges from what the model assumes |

---

## Architecture (at a glance)

```text
ingestion → research → planning → patch → validation ─┬→ PR / dry-run
         └ failures ───────────────────→ human_review / terminal failure
```

- **Ingestion:** Issue metadata + **pinned `base_commit_sha`** (default branch tip unless overridden).
- **Research:** LLM-suggested candidates augmented by **sanitized code search** and **tree-sitter symbol extraction** (Python-focused today).
- **Planning:** Fix strategy, risk, ambiguity flags—may route to human review before patching.
- **Patch:** JSON **`file_changes`** (path + search + replace) built using **file snapshots from GitHub at the pinned SHA**.
- **Validation:** Clone at that SHA, apply edits deterministically, optional generated test module, run pytest / Ruff / Mypy inside Docker.
- **Terminal nodes:** Open PR, dry-run artifacts, human escalation, or hard failure.

---

## Quickstart

```bash
cd multi-agent-code-repair
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Set GITHUB_TOKEN and model provider keys in .env
```

Build the sandbox image (required for validation):

```bash
docker build -t multi-agent-sandbox:latest -f docker/Dockerfile.sandbox .
```

Run the graph:

```bash
python main.py run --issue-url "https://github.com/owner/repo/issues/123"
```

Dry-run (no PR; prints patch summary and template payload):

```bash
python main.py run --issue-url "https://github.com/owner/repo/issues/123" --dry-run
```

Batch benchmark:

```bash
python main.py evaluate --benchmark-file evaluation/benchmark_issues.json
```

---

## Technical decisions

**Why LangGraph instead of a linear chain?**  
Repair is inherently **stateful**: validation stderr, exit codes, and retry counts feed back into the patch node on the next hop. Typed routing reads structured fields (`tests_passed`, `retry_count`, …), not free-form prose.

**Why structured search/replace instead of unified diff?**  
`git apply` breaks when hunks do not match the pinned tree—often because models hallucinate context lines. **Search/replace grounded in fetched file bodies at `base_commit_sha`** aligns the model with reality and shrinks an entire class of merge-style failures.

**Why Pydantic at node boundaries?**  
Structured outputs keep contracts explicit; checkpoint serde stores plain dicts and **`as_model()`** rehydrates them so routing and nodes stay type-safe after resume.

**Why SQLite checkpointing?**  
`SqliteSaver` persists graph checkpoints under `checkpoints/` (ignored by git). Reusing the same **`thread_id`** lets you resume after the last completed node instead of restarting cold.

**Why Docker with network isolation and quotas?**  
Untrusted generated code runs with bounded CPU/memory and (by default) **no container network**, reducing exfiltration and surprise installs.

**Why LiteLLM?**  
One surface for multiple providers; per-stage overrides via **`RESEARCH_MODEL`**, **`PLANNING_MODEL`**, **`PATCH_MODEL`**, or **`LLM_MODEL`**.

**Where LLMs are deliberately not used**  
Issue ingestion, repo reads, symbol extraction, **deterministic application of `file_changes`**, sandbox execution, git operations, and PR creation stay non-LLM to control cost, latency, and failure modes.

**Why `base_commit_sha` pinning?**  
Research excerpts, fetched patch inputs, and the validation clone must all refer to the **same revision**. Without a pin, fast-moving default branches cause silent skew between what was read and what was executed.

**Patch hygiene (`tools/patch_sanity.py`)**  
Fast deterministic rules—empty search strings, no-op replacements, forbidden direct edits under `tests/` (tests belong in `tests_written`)—are encoded here and covered by unit tests so risky shapes are documented and regressions are caught in CI.

---

## Repository layout

| Path | Role |
|------|------|
| `main.py` | CLI (`run`, `evaluate`) |
| `graph/` | Graph compilation, shared state, routing |
| `nodes/` | Node implementations (LLM + deterministic) |
| `prompts/` | Prompt builders |
| `tools/` | GitHub, Docker sandbox, templates, patch helpers |
| `docker/` | Sandbox image |
| `evaluation/` | Benchmark harness and datasets |
| `tests/` | Pytest suite (routing, sandbox markers, patch rules, integration) |

---

## Contributing & operator docs

**[`CLAUDE.md`](CLAUDE.md)** is the implementation guide for contributors and coding agents: state contracts, routing invariants, sandbox assumptions, and safe change patterns.

For end-to-end benchmark numbers and run logs, see **`RESULTS.md`**.

---

### Demo (recommended for portfolios)

A short screen recording (issue URL → node progression → validation summary) materially improves how quickly reviewers understand the system. Add a link or GIF above the quickstart when you have one.
