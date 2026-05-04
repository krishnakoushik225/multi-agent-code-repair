from __future__ import annotations

import json
import os

from litellm import completion

from graph.state import GraphState, IssueContext, PatchOutput, PlanningOutput, ResearchOutput, ValidationOutput, as_model
from logging_config import get_logger
from prompts.patch_prompt import build_patch_prompt, build_patch_repair_prompt
from tools.patch_sanity import sanity_check_unified_diff

logger = get_logger(__name__)


def patch_node(state: GraphState) -> dict:
    """LLM agent. Generates unified diff. On retry, receives prior stderr in context."""
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

    prompt = build_patch_prompt(ctx, research, planning, prior_error)
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

    output = PatchOutput(
        unified_diff=str(llm_output.get("unified_diff", "")),
        files_modified=list(llm_output.get("files_modified", [])),
        explanation=str(llm_output.get("explanation", "")),
        tests_written=llm_output.get("tests_written"),
    )

    sanity_issues = sanity_check_unified_diff(output.unified_diff)
    if sanity_issues:
        repair_prompt = build_patch_repair_prompt(
            ctx, research, planning, sanity_issues, output.unified_diff
        )
        repair_resp = completion(
            model=model,
            messages=[{"role": "user", "content": repair_prompt}],
            response_format={"type": "json_object"},
        )
        repair_content = repair_resp.choices[0].message.content or "{}"
        try:
            repaired_raw = json.loads(repair_content)
        except json.JSONDecodeError:
            pass
        else:
            candidate = PatchOutput(
                unified_diff=str(repaired_raw.get("unified_diff", "")),
                files_modified=list(repaired_raw.get("files_modified", [])),
                explanation=str(repaired_raw.get("explanation", output.explanation)),
                tests_written=repaired_raw.get("tests_written", output.tests_written),
            )
            if not sanity_check_unified_diff(candidate.unified_diff):
                output = candidate

    new_retry = retry_count + 1 if prior_error is not None else retry_count
    logger.info(
        "node complete",
        extra={
            "output_payload": {
                "files_modified_count": len(output.files_modified),
                "unified_diff_chars": len(output.unified_diff or ""),
                "has_tests_written": output.tests_written is not None,
                "retry_count_after": new_retry,
            },
        },
    )
    return {
        "patch_output": output,
        "retry_count": new_retry,
    }
