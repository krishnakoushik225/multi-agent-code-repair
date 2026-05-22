from __future__ import annotations

from graph.state import IssueContext, ResearchOutput

_MAX_FILES_LISTED = 20
_MAX_SYMBOLS = 40
_MAX_CODE_FILES = 5
_MAX_FILE_CHARS = 4_000


def build_planning_prompt(ctx: IssueContext, research: ResearchOutput) -> str:
    files = "\n".join(f"- {p}" for p in research.relevant_files[:_MAX_FILES_LISTED])
    symbols = ", ".join(research.related_symbols[:_MAX_SYMBOLS])
    snippets = []
    for path, content in list(research.file_contents.items())[:_MAX_CODE_FILES]:
        snippets.append(f"### {path}\n```\n{content[:_MAX_FILE_CHARS]}\n```")
    code_blocks = "\n".join(snippets)

    return f"""You are planning a minimal, safe code fix.

Issue #{ctx.issue_number}: {ctx.title}

Summary:
{research.issue_summary}

Relevant files:
{files}

Related symbols: {symbols}

Code excerpts:
{code_blocks}

Return STRICT JSON with keys:
- fix_strategy: string
- candidate_files: string[] (files you expect to modify)
- estimated_lines_changed: integer
- risk_level: one of "low", "medium", "high"
- requires_new_tests: boolean
- ambiguous: boolean
- ambiguity_reason: string or null
"""
