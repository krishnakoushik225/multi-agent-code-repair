from __future__ import annotations

from typing import Any

from graph.state import IssueContext, PlanningOutput, ResearchOutput


def build_patch_prompt(
    ctx: IssueContext,
    research: ResearchOutput,
    planning: PlanningOutput,
    pinned_file_contents: dict[str, str],
    prior_error: dict[str, Any] | None = None,
) -> str:
    _ = research
    files_block = ""
    for path, content in (pinned_file_contents or {}).items():
        truncated = content[:6000] + "\n... (truncated)" if len(content) > 6000 else content
        files_block += f"\n=== {path} ===\n{truncated}\n"

    retry_block = ""
    if prior_error:
        retry_block = f"""
PREVIOUS ATTEMPT FAILED — Apply errors:
{prior_error.get('stderr', '')[:1000]}

The search string was not found verbatim. Check your search string character by character against the file content shown above. Copy the search string directly from the file — do not paraphrase or reformat it.
"""

    return f"""You are a precise code repair agent. Output ONLY a JSON object, no markdown, no explanation outside the JSON.

ISSUE #{ctx.issue_number}: {ctx.title}
{ctx.body[:1000]}

FIX STRATEGY: {planning.fix_strategy}
FILES TO MODIFY: {', '.join(planning.candidate_files)}

EXACT FILE CONTENTS (copy search strings verbatim from these):
{files_block}

{retry_block}

OUTPUT FORMAT — return exactly this JSON structure:
{{
  "file_changes": [
    {{
      "path": "src/click/core.py",
      "search": "exact string from the file to find — copy character by character",
      "replace": "replacement string",
      "description": "one sentence explaining this change"
    }}
  ],
  "explanation": "why this fixes the issue",
  "tests_written": "python test code as a string, or null"
}}

CRITICAL RULES FOR search STRINGS:
1. Copy the search string EXACTLY from the file content shown above — same indentation, same spacing, same line endings.
2. Include enough surrounding lines (5-10) to uniquely identify the location.
3. Never paraphrase, reformat, or reconstruct from memory.
4. If you cannot find the exact text in the file content above, do not include that change.
5. Each search string must appear exactly once in the file. If it appears multiple times, add more context lines to make it unique.

RULES FOR tests_written:
The tests_written string must be a complete, self-contained Python file. Always start with all necessary imports. For click tests, always include: import click and from click import Command, Group, Option, Argument and from click.testing import CliRunner at the top of the file. Never reference names that are not imported in the same tests_written string.
"""
