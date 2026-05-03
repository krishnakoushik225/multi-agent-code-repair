from __future__ import annotations

from graph.state import IssueContext


def build_research_prompt(ctx: IssueContext, repo_tree: list[str]) -> str:
    tree_preview = "\n".join(repo_tree[:400])
    if len(repo_tree) > 400:
        tree_preview += f"\n... ({len(repo_tree) - 400} more paths truncated)"

    return f"""You are a senior engineer triaging a GitHub issue.

Repository: {ctx.repo_owner}/{ctx.repo_name}
Issue #{ctx.issue_number}: {ctx.title}

Body:
{ctx.body}

Labels: {", ".join(ctx.labels) if ctx.labels else "(none)"}

Repository file paths (sample):
{tree_preview}

Return STRICT JSON with keys:
- candidate_files: string[] (relative paths, max 10, prefer Python source)
- issue_summary: string (one technical paragraph)
- confidence_score: number between 0 and 1

Pick candidate_files that are most likely related to the bug. Prefer paths seen in the tree sample.
"""
