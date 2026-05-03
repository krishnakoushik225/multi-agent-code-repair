from __future__ import annotations

from graph.state import IssueContext, ResearchOutput


def build_planning_prompt(ctx: IssueContext, research: ResearchOutput) -> str:
    files = "\n".join(f"- {p}" for p in research.relevant_files[:20])
    symbols = ", ".join(research.related_symbols[:40])
    snippets = []
    for path, content in list(research.file_contents.items())[:5]:
        snippets.append(f"### {path}\n```\n{content[:4000]}\n```")
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
