from __future__ import annotations

from typing import Any

from graph.state import IssueContext, PlanningOutput, ResearchOutput


def build_patch_prompt(
    ctx: IssueContext,
    research: ResearchOutput,
    planning: PlanningOutput,
    prior_error: dict[str, Any] | None,
) -> str:
    err = ""
    if prior_error:
        err = f"""
Previous validation attempt failed.

Attempt: {prior_error.get("attempt")}
stdout (excerpt):
{prior_error.get("stdout", "")[-8000:]}

stderr (excerpt):
{prior_error.get("stderr", "")[-8000:]}
"""

    files = "\n".join(f"- {p}" for p in planning.candidate_files)
    snippets = []
    for path in planning.candidate_files[:8]:
        content = research.file_contents.get(path)
        if content:
            snippets.append(f"### {path}\n```\n{content[:12000]}\n```")
    code_blocks = "\n".join(snippets)

    base = ctx.base_commit_sha or "(default branch tip)"
    return f"""You produce a unified diff (git apply compatible) for the following GitHub issue.

The file excerpts below are from repository commit **{base}**. Your diff MUST apply cleanly to that exact revision (same line numbers and context as in the excerpts).

Issue #{ctx.issue_number}: {ctx.title}

Issue body:
{ctx.body}

Planning strategy:
{planning.fix_strategy}

Candidate files:
{files}

Code context:
{code_blocks}
{err}

Return STRICT JSON with keys:
- unified_diff: string (complete unified diff for all modified files)
- files_modified: string[] (paths modified by the diff)
- explanation: string
- tests_written: string or null (REQUIRED when adding tests: full pytest module body for tests/test_auto_generated.py)

Rules for unified_diff — read carefully, violations cause `git apply` to fail:
- **CRITICAL:** Do NOT include any file under `tests/` in `unified_diff` or `files_modified`. GitHub-style test edits belong in `tests_written` only (saved as tests/test_auto_generated.py). Modifying tests/test_*.py in a unified diff is the #1 cause of corrupt patches.
- Only patch library/source paths (e.g. `src/`, project package dirs) and optionally docs/changelog if needed. Prefer minimal `src/`-only changes.
- The diff must apply cleanly with `git apply` against the UNMODIFIED tree at commit {base}.
- If you modify the same file in multiple places, combine all hunks for that file under a SINGLE `diff --git` header. Never emit two separate `diff --git a/foo.py b/foo.py` headers for the same file — that produces a corrupt patch.
- Do NOT generate stacked/sequential diffs (where the second diff's base is the output of the first). Every diff header must be relative to the original tree at {base}.
- Use standard unified diff format: `diff --git a/<path> b/<path>` header, then `--- a/<path>` / `+++ b/<path>`, then `@@ ... @@` hunks.
- Omit the `index <sha>..<sha>` lines — they are optional and you may get them wrong.
- Each `@@ -L,N +L,N @@` line must have exactly N unchanged context lines, minus-lines, and plus-lines matching the source. Do not wrap or break lines inside hunks; every context line must match byte-for-byte (including spaces).
- Never insert Sphinx/reStructuredText directives (lines starting with `.. `) into executable Python code unless they are inside a properly opened and indented docstring block in that file.
- Never emit incomplete statements (e.g. `x =` with no right-hand side, or a `+` line that is only part of a continued expression).
- Prefer the smallest change that fixes the issue.
- If you add tests, put them in `tests_written` as a full file body (saved as tests/test_auto_generated.py). Never put test code in `unified_diff`.
- For `tests_written`, avoid extremely long lines (many repos use Ruff E501 at 88); split long `assert "..."` strings or use shorter substrings so `ruff check` can pass.
"""


def build_patch_repair_prompt(
    ctx: IssueContext,
    research: ResearchOutput,
    planning: PlanningOutput,
    issues: list[str],
    bad_unified_diff: str,
) -> str:
    excerpt = bad_unified_diff[:60000]
    if len(bad_unified_diff) > 60000:
        excerpt += "\n\n[... diff truncated for repair prompt ...]\n"

    base = ctx.base_commit_sha or "(default branch tip)"
    return f"""You previously produced a unified diff that failed validation checks before git apply.

Repository commit: {base}

Validation issues (fix all):
{chr(10).join(f"- {i}" for i in issues)}

Broken unified_diff (repair this — output a complete replacement):
{excerpt}

Issue #{ctx.issue_number}: {ctx.title}
Planning: {planning.fix_strategy}

Return STRICT JSON with the same keys as before:
- unified_diff (must pass: no tests/ paths, no incomplete lines in + lines, git apply clean at {base})
- files_modified (no paths under tests/)
- explanation
- tests_written (full pytest file if tests are needed; null otherwise)
"""
