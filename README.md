# Multi-Agent Code Repair Orchestration

LangGraph workflow that ingests a GitHub issue, researches the codebase with deterministic tooling plus LLM planning, generates a patch, validates it in a Docker sandbox (pytest, ruff, mypy), retries on structured failure signals, and opens a pull request.

## Quickstart

```bash
cd multi-agent-code-repair
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Build the sandbox image (required for validation):

```bash
docker build -t multi-agent-sandbox:latest -f docker/Dockerfile.sandbox .
```

Run the graph:

```bash
python main.py run --issue-url "https://github.com/owner/repo/issues/123"
```

Benchmark harness:

```bash
python main.py evaluate --benchmark-file evaluation/benchmark_issues.json
```

## Technical Decisions

**Why LangGraph over a simple chain?**  
Real repair workflows are stateful. When tests fail in the Docker sandbox, stderr and exit codes are merged back into graph state and the patch node consumes them on the next hop. A linear chain would need brittle prompt stitching instead of typed routing.

**Why Pydantic for inter-node handoffs?**  
Structured outputs keep conditional edges honest: routing reads booleans and integers (`tests_passed`, `retry_count`) instead of parsing model prose.

**Why SQLite checkpointing?**  
`SqliteSaver` persists checkpoints under `checkpoints/graph.db`. Reusing the same `thread_id` lets a resumed process continue after the last completed node instead of restarting cold.

**Why Docker with `network=none`?**  
Generated code runs in isolation with bounded CPU and memory. Disabling network access inside the sandbox reduces exfiltration and surprise dependency installs.

**Why LiteLLM?**  
One configuration surface for multiple providers. Swap models with environment variables (`RESEARCH_MODEL`, `PLANNING_MODEL`, `PATCH_MODEL`, `LLM_MODEL`).

**Where we deliberately avoid LLMs**  
Issue ingestion, repository reads, AST symbol extraction, diff application, sandbox execution, git push, and PR creation stay deterministic to reduce cost, latency, and failure modes.

**Why `as_model()` instead of direct dict access?**  
LangGraph checkpoints persist state through SQLite serde: Pydantic objects round-trip as plain `dict` values. `as_model()` rehydrates those dicts back into typed models so node code and routing logic keep field access, enums, and validation consistent without sprinkling ad hoc `dict` parsing at every edge.

**Why a two-pass patch generation (sanity check + repair)?**  
`patch_sanity.py` catches deterministic unified-diff failure modes (for example corrupt hunks or forbidden `tests/` paths) before any clone or Docker run. When sanity fails, a second LLM call with a repair prompt regenerates the diff, which cuts expensive sandbox invocations and shortens the feedback loop for formatting-only mistakes.

**Why `base_commit_sha` pinning?**  
The base SHA is fixed at ingestion so research excerpts, the generated patch, and `git apply` / validation all target the same tree. On fast-moving default branches, otherwise research could read one revision while validation applies against another, producing spurious context mismatches and flaky applies.

## Project layout

See the repository tree under `graph/`, `nodes/`, `tools/`, `prompts/`, `docker/`, `evaluation/`, and `tests/` for the modules referenced in the design brief.
