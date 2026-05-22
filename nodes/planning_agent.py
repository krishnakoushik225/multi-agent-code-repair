from __future__ import annotations

import json
import os

from litellm import completion

from graph.state import (
    GraphState,
    IssueContext,
    PlanningOutput,
    ResearchOutput,
    RiskLevel,
    as_model,
)
from logging_config import get_logger
from prompts.planning_prompt import build_planning_prompt

logger = get_logger(__name__)


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(value)  # type: ignore[call-overload]
    except (TypeError, ValueError):
        return default


def planning_node(state: GraphState) -> dict:
    """LLM agent. Decides fix strategy, risk level, and whether new tests are needed."""
    logger.info("node starting")
    raw_ctx = state["issue_context"]
    raw_research = state["research_output"]
    if raw_ctx is None or raw_research is None:
        logger.error("Missing issue_context or research_output")
        return {
            "error_message": "Missing issue_context or research_output",
            "final_status": "failed",
        }

    ctx = as_model(IssueContext, raw_ctx)
    research = as_model(ResearchOutput, raw_research)

    prompt = build_planning_prompt(ctx, research)
    model = os.environ.get("PLANNING_MODEL", os.environ.get("LLM_MODEL", "gpt-4o"))
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

    raw_risk = str(llm_output.get("risk_level", "medium")).lower()
    try:
        risk_level = RiskLevel(raw_risk)
    except ValueError:
        risk_level = RiskLevel.MEDIUM

    output = PlanningOutput(
        fix_strategy=str(llm_output.get("fix_strategy", "No strategy provided")),
        candidate_files=list(llm_output.get("candidate_files", [])),
        estimated_lines_changed=_safe_int(llm_output.get("estimated_lines_changed"), default=10),
        risk_level=risk_level,
        requires_new_tests=bool(llm_output.get("requires_new_tests", True)),
        ambiguous=bool(llm_output.get("ambiguous", False)),
        ambiguity_reason=llm_output.get("ambiguity_reason"),
    )

    logger.info(
        "node complete",
        extra={
            "output_payload": {
                "risk_level": output.risk_level.value,
                "ambiguous": output.ambiguous,
                "candidate_files_count": len(output.candidate_files),
                "requires_new_tests": output.requires_new_tests,
            },
        },
    )
    return {"planning_output": output}
