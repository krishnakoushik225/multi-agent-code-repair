from __future__ import annotations

import json
import os

from litellm import completion

from graph.state import GraphState, IssueContext, ResearchOutput, as_model
from logging_config import get_logger
from prompts.research_prompt import build_research_prompt
from tools.code_search import find_related_symbols
from tools.github_tools import get_file_content, get_repo_tree, search_code_in_repo

logger = get_logger(__name__)

_MAX_CANDIDATE_FILES = 10
_MAX_SEARCH_QUERY_CHARS = 256


def research_node(state: GraphState) -> dict:
    """LLM agent. Uses GitHub Search API and tree-sitter to find relevant code."""
    logger.info("node starting")
    raw_ctx = state["issue_context"]
    if raw_ctx is None:
        logger.error("Missing issue_context")
        return {"error_message": "Missing issue_context", "final_status": "failed"}

    ctx = as_model(IssueContext, raw_ctx)

    git_ref = ctx.base_commit_sha or None
    repo_tree = get_repo_tree(ctx.repo_owner, ctx.repo_name, git_ref=git_ref)
    prompt = build_research_prompt(ctx, repo_tree)

    model = os.environ.get("RESEARCH_MODEL", os.environ.get("LLM_MODEL", "gpt-4o"))
    timeout = float(os.environ.get("LLM_TIMEOUT", "120"))
    num_retries = int(os.environ.get("LLM_NUM_RETRIES", "2"))
    response = completion(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
        timeout=timeout,
        num_retries=num_retries,
    )
    content = response.choices[0].message.content or "{}"
    try:
        llm_output = json.loads(content)
    except json.JSONDecodeError:
        logger.error("LLM returned invalid JSON: %s", content[:200])
        return {
            "error_message": f"LLM returned invalid JSON: {content[:200]}",
            "final_status": "failed",
        }

    candidate_files = list(dict.fromkeys(llm_output.get("candidate_files", [])))

    query = f"{ctx.title} {ctx.body}"[:_MAX_SEARCH_QUERY_CHARS]
    for p in search_code_in_repo(ctx.repo_owner, ctx.repo_name, query):
        if p not in candidate_files:
            candidate_files.append(p)

    file_contents: dict[str, str] = {}
    for file_path in candidate_files[:_MAX_CANDIDATE_FILES]:
        content_text = get_file_content(ctx.repo_owner, ctx.repo_name, file_path, ref=git_ref)
        if content_text:
            file_contents[file_path] = content_text

    related_symbols = find_related_symbols(file_contents, ctx.title + " " + ctx.body)

    output = ResearchOutput(
        relevant_files=list(file_contents.keys()),
        file_contents=file_contents,
        related_symbols=related_symbols,
        issue_summary=str(llm_output.get("issue_summary", "")),
        confidence_score=float(llm_output.get("confidence_score", 0.5)),
    )

    logger.info(
        "node complete",
        extra={
            "output_payload": {
                "relevant_files_count": len(output.relevant_files),
                "related_symbols_count": len(output.related_symbols),
                "confidence_score": output.confidence_score,
            },
        },
    )
    return {"research_output": output}
