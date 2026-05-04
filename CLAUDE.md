# CLAUDE.md

This document is an implementation-level guide for AI/code agents and contributors working on `multi-agent-code-repair`.
It describes how the system is wired today, what assumptions it makes, and where changes are safest.

## 1) Project purpose

`multi-agent-code-repair` orchestrates a multi-step workflow that:

1. Ingests a GitHub issue.
2. Researches likely relevant files/symbols using deterministic tools plus an LLM.
3. Plans a minimal fix.
4. Generates a unified diff patch.
5. Validates the patch in an isolated Docker sandbox (`pytest`, `ruff`, `mypy`).
6. Retries patch generation with structured failure feedback until success or retry budget is exhausted.
7. Opens a PR (or prints dry-run artifacts).

Core design goal: deterministic boundaries around expensive or risky operations (GitHub API, repo reads, patch apply, validation, git push/PR create), while using LLMs only for semantic reasoning steps.

## 2) High-level architecture

### Runtime stack

- Python `>=3.10`
- LangGraph state machine + SQLite checkpointing
- LiteLLM for provider/model abstraction
- PyGithub for GitHub issue/repo/PR operations
- Docker SDK for sandboxed validation
- Tree-sitter (Python grammar) for symbol extraction
- Typer + Rich for CLI and console reporting

Primary dependency declarations:
- `pyproject.toml` (PEP 621 metadata and tool config)
- `requirements.txt` (quickstart installation path)

### Repository layout

- `main.py`: CLI entrypoint (`run`, `evaluate`)
- `graph/`: graph wiring, routing edges, typed shared state
- `nodes/`: node implementations (LLM and deterministic)
- `tools/`: deterministic utilities/integrations
- `prompts/`: prompt builders for LLM nodes
- `docker/`: sandbox image and validation entrypoint
- `evaluation/`: benchmark harness + metric summarization
- `tests/`: unit/integration checks

## 3) End-to-end execution flow

The graph is compiled in `graph/graph_builder.py` with SQLite checkpoint persistence at `checkpoints/graph.db`.

Node sequence and routes:

1. `ingestion`
   - Parses issue URL and fetches issue/repo metadata.
   - Pins base commit SHA (default branch tip unless `--base-sha` override).
   - On failure routes to `failed`.

2. `research`
   - LLM suggests candidate files and issue summary from repo tree sample.
   - Deterministic GitHub code search augments candidate file list.
   - Deterministic file content fetch + tree-sitter symbol extraction.

3. `planning`
   - LLM outputs fix strategy, risk level, ambiguity flags, candidate files.
   - If `ambiguous=true` and `risk_level=high`, route to `human_review`.

4. `patch`
   - LLM generates strict JSON with `unified_diff`, `files_modified`, `explanation`, optional `tests_written`.
   - Deterministic `patch_sanity` checks run.
   - If sanity fails, a second repair prompt is used to regenerate a valid diff.
   - On retry paths, receives prior validation stdout/stderr excerpts.

5. `validation`
   - Deterministically clones repo at pinned commit/branch.
   - Applies unified diff with `git apply --recount`.
   - Writes `tests/test_auto_generated.py` if `tests_written` exists.
   - Runs Docker container to execute `pytest`, `ruff check`, `mypy`.
   - Parses sentinel markers (`TEST_EXIT`, `LINT_EXIT`, `TYPE_EXIT`).
   - Routing:
     - all pass -> `pr` or `dry_run`
     - fail and retries remain -> `patch`
     - fail and retries exhausted -> `human_review`

6. Terminal nodes
   - `pr`: push branch and open GitHub PR
   - `dry_run`: print diff + PR template payload and stop
   - `human_review`: explicit escalation state
   - `failed`: deterministic hard failure state

## 4) Core state and contracts

Shared graph state lives in `graph/state.py` as TypedDict + Pydantic models:

- `IssueContext`
- `ResearchOutput`
- `PlanningOutput`
- `PatchOutput`
- `ValidationOutput`
- `PROutput`
- enums: `RiskLevel`, `RoutingDecision`

Checkpoint round-tripping:
- `as_model()` rehydrates dicts into Pydantic models after checkpoint restore.
- `graph_builder.py` configures explicit msgpack allowlist for serialized model classes to avoid strict deserialization breakages.

LLM output contracts:
- All LLM nodes request JSON object output (`response_format={"type":"json_object"}`).
- Prompt builders in `prompts/` define required keys.
- Node code performs defensive JSON parsing and fails fast on malformed content.

Patch-specific contract:
- `unified_diff` must be git-apply compatible.
- `tests/` paths are prohibited inside `unified_diff` and must instead go to `tests_written`.
- Common malformed patterns are rejected by deterministic sanity checks.

## 5) Configuration surfaces

### Environment variables

Required:
- `GITHUB_TOKEN`

Model selection:
- `LLM_MODEL` (global default)
- `RESEARCH_MODEL`, `PLANNING_MODEL`, `PATCH_MODEL` (per-stage overrides)

Sandbox controls:
- `SANDBOX_IMAGE` (default `multi-agent-sandbox:latest`)
- `SANDBOX_CLONE_TIMEOUT` (default `300`)
- `SANDBOX_DOCKER_NETWORK` (default `none`)

Optional tracing:
- `LANGCHAIN_TRACING_V2`
- `LANGCHAIN_API_KEY`
- `LANGCHAIN_PROJECT`

Note: `.env.example` includes `PR_DRY_RUN`, but runtime dry-run behavior is controlled by CLI `--dry-run`.

### CLI

`python main.py run --issue-url <url> [--max-retries N] [--model MODEL] [--dry-run] [--base-sha SHA]`

`python main.py evaluate --benchmark-file evaluation/benchmark_issues.json`

Threading/checkpoint key:
- `thread_id` is derived from issue URL (+ base SHA prefix if pinned), so reruns can recover/continue through checkpoints.

## 6) Deterministic tooling behavior

### GitHub tooling (`tools/github_tools.py`)

- Fetches bounded repo tree (`max_paths=800`) at a specific commit.
- Fetches file content with branch/commit ref support.
- Performs sanitized repository-scoped code search (gracefully degrades on API errors).
- For PR creation path:
  - clones with authenticated URL
  - checks out pinned base
  - creates branch
  - applies patch
  - commits with bot identity
  - pushes branch

### Docker sandbox (`tools/docker_sandbox.py`)

Validation invariants:
- Reject empty/malformed diffs before clone.
- Hard resource constraints:
  - memory `512m`
  - CPU quota ~0.5 core
  - optional network isolation (default `none`)
- Expects entrypoint markers:
  - `TEST_EXIT=<code>`
  - `LINT_EXIT=<code>`
  - `TYPE_EXIT=<code>`

Failure behavior:
- Any clone/checkout/apply/container failure maps to non-zero test/lint/type codes and structured stderr for retry reasoning.

### Patch sanity (`tools/patch_sanity.py`)

Fast pre-apply checks for known LLM failure modes:
- test-file edits in diff
- incomplete assertions/assignments
- malformed call syntax patterns

## 7) Prompting strategy

Prompts live in `prompts/` and are intentionally role-scoped:

- `research_prompt.py`: issue triage + candidate file shortlist
- `planning_prompt.py`: minimal/safe strategy and risk framing
- `patch_prompt.py`: strict diff generation rules
  - includes anti-corruption rules (single header per file, no stacked diffs, no `index` lines, exact context discipline)
  - includes retry feedback excerpts from prior validation
  - includes explicit repair prompt for malformed diff outputs

This setup keeps each LLM call narrow and composable, reducing prompt bloat and making failures easier to attribute.

## 8) Testing and quality gates

Local quality gates run in sandbox entrypoint:
- `pytest`
- `ruff format --check .`
- `ruff check .`
- `mypy .`

Current test coverage focus:
- graph routing behavior (`tests/test_edges.py`)
- patch retry semantics and mini-checkpoint behavior (`tests/test_graph_integration.py`)
- ingestion URL/token/base-sha scenarios (`tests/test_ingestion.py`)
- patch sanity rules (`tests/test_patch_sanity.py`)
- sandbox marker parser (`tests/test_docker_sandbox.py`)

Coverage gaps to keep in mind:
- No full end-to-end test that exercises live GitHub + Docker + PR creation.
- Limited tests for prompt-builder output shapes and truncation behavior.
- Symbol search is Python-focused; non-Python repos are under-tested.

## 9) Evaluation harness

`evaluation/benchmark_runner.py` runs batch issues from JSON and summarizes:
- final status
- PR-opened indicator
- tests-passed indicator
- runtime seconds
- optional human edits / cost metadata from dataset

Useful for regression tracking across orchestration changes and prompt iterations.

## 10) Operational runbook

### First-time setup

1. Create virtualenv and install dependencies.
2. Copy `.env.example` to `.env` and set `GITHUB_TOKEN`.
3. Build sandbox image:
   - `docker build -t multi-agent-sandbox:latest -f docker/Dockerfile.sandbox .`

### Typical execution

- Dry-run safety:
  - `python main.py run --issue-url "<issue-url>" --dry-run`
- PR-opening mode:
  - `python main.py run --issue-url "<issue-url>"`
- Benchmark mode:
  - `python main.py evaluate --benchmark-file evaluation/benchmark_issues.json`

### Failure triage priorities

1. Missing/invalid auth (`GITHUB_TOKEN`) or model provider credentials.
2. Docker daemon/image availability.
3. Diff corruption (`git apply` failures, sanity check errors).
4. Real test/lint/type regressions requiring patch iteration.
5. High-risk ambiguous plans requiring manual review.

## 11) Architectural assumptions and limitations

- Primary happy path assumes Python-heavy target repos (tree-sitter support currently Python only).
- Validation clones target repositories on host before containerized checks.
- No built-in hosted CI config in this repo; quality is currently a local/run-time concern.
- Some docs/config drift exists (example env includes an unused `PR_DRY_RUN` variable).
- Runtime artifacts (for example, verbose logs) may appear in repo and should be curated for hygiene.

## 12) Safe change guidance for contributors/agents

When modifying this codebase:

1. Preserve typed state contracts first (`graph/state.py`) before changing node payloads.
2. Keep routing logic (`graph/edges.py`) and graph mapping (`graph_builder.py`) synchronized.
3. Treat `tools/docker_sandbox.py` as a critical trust boundary:
   - avoid weakening isolation/resource limits without explicit rationale.
4. Maintain deterministic checks around patch validity before expensive actions.
5. If prompt formats change, update node JSON parsing and related tests together.
6. Prefer backward-compatible additions to state to avoid checkpoint replay issues.
7. Keep retries bounded and explicit; do not add hidden loops in individual nodes.

## 13) Recommended reading order for new contributors

1. `README.md`
2. `main.py`
3. `graph/state.py`
4. `graph/graph_builder.py`
5. `graph/edges.py`
6. `nodes/patch_agent.py`
7. `nodes/validation_node.py`
8. `tools/docker_sandbox.py`
9. `tools/github_tools.py`
10. `tests/test_graph_integration.py` and `tests/test_edges.py`

This order explains intent first, then workflow wiring, then safety-critical execution, then behavior locks in tests.
