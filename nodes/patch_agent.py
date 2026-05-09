from __future__ import annotations

import json
import os

from litellm import completion

from graph.state import (
    FileChange,
    GraphState,
    IssueContext,
    PatchOutput,
    PlanningOutput,
    ResearchOutput,
    ValidationOutput,
    as_model,
)
from logging_config import get_logger
from prompts.patch_prompt import build_patch_prompt
from tools.github_tools import get_file_content

logger = get_logger(__name__)


def patch_node(state: GraphState) -> dict:
    """LLM agent. Generates structured file_changes. On retry, receives prior stderr in context."""
    logger.info("node starting")
    raw_ctx = state["issue_context"]
    raw_research = state["research_output"]
    raw_planning = state["planning_output"]
    if raw_ctx is None or raw_research is None or raw_planning is None:
        logger.error("Missing upstream context for patch")
        return {"error_message": "Missing upstream context for patch", "final_status": "failed"}

    ctx = as_model(IssueContext, raw_ctx)
    research = as_model(ResearchOutput, raw_research)
    planning = as_model(PlanningOutput, raw_planning)

    raw_validation = state.get("validation_output")
    validation = as_model(ValidationOutput, raw_validation) if raw_validation is not None else None
    retry_count = int(state.get("retry_count", 0))

    prior_error = None
    if validation is not None and not (
        validation.tests_passed and validation.lint_passed and validation.type_check_passed
    ):
        prior_error = {
            "stderr": validation.stderr,
            "stdout": validation.stdout,
            "attempt": retry_count,
        }

    pinned_file_contents: dict[str, str] = {}
    for file_path in planning.candidate_files:
        content_text = get_file_content(
            ctx.repo_owner,
            ctx.repo_name,
            file_path,
            ref=ctx.base_commit_sha or None,
        )
        if content_text:
            pinned_file_contents[file_path] = content_text

    prompt = build_patch_prompt(ctx, research, planning, pinned_file_contents, prior_error)
    model = os.environ.get("PATCH_MODEL", os.environ.get("LLM_MODEL", "gpt-4o"))
    response = completion(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        response_format={"type": "json_object"},
    )
    content = response.choices[0].message.content or "{}"
    try:
        llm_output = json.loads(content)
    except json.JSONDecodeError:
        logger.error("LLM returned invalid JSON: %s", content[:200])
        return {"error_message": f"LLM returned invalid JSON: {content[:200]}", "final_status": "failed"}

    raw_changes = llm_output.get("file_changes", [])
    if not isinstance(raw_changes, list):
        logger.error("LLM returned invalid file_changes payload")
        return {"error_message": "LLM returned invalid file_changes payload", "final_status": "failed"}
    file_changes: list[FileChange] = []
    for item in raw_changes:
        try:
            file_changes.append(FileChange.model_validate(item))
        except Exception as exc:  # noqa: BLE001
            logger.error("Invalid file change from LLM: %s", exc)
            return {"error_message": f"Invalid file change from LLM: {exc}", "final_status": "failed"}

    output = PatchOutput(
        file_changes=file_changes,
        explanation=str(llm_output.get("explanation", "")),
        tests_written=llm_output.get("tests_written"),
    )

    new_retry = retry_count + 1 if prior_error is not None else retry_count
    logger.info(
        "node complete",
        extra={
            "output_payload": {
                "file_changes_count": len(output.file_changes),
                "has_tests_written": output.tests_written is not None,
                "retry_count_after": new_retry,
            },
        },
    )
    return {
        "patch_output": output,
        "retry_count": new_retry,
    }
