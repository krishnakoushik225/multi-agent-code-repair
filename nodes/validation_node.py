from __future__ import annotations

from graph.state import (
    GraphState,
    IssueContext,
    PatchOutput,
    RoutingDecision,
    ValidationOutput,
    as_model,
)
from logging_config import get_logger
from tools.docker_sandbox import apply_patch_and_run_tests

logger = get_logger(__name__)


def validation_node(state: GraphState) -> dict:
    """Deterministic node. Applies patch in Docker sandbox and runs tests."""
    logger.info("node starting")
    raw_ctx = state["issue_context"]
    raw_patch = state["patch_output"]
    if raw_ctx is None or raw_patch is None:
        logger.error("Missing issue_context or patch_output")
        return {"error_message": "Missing issue_context or patch_output", "final_status": "failed"}

    ctx = as_model(IssueContext, raw_ctx)
    patch = as_model(PatchOutput, raw_patch)

    retry_count = int(state.get("retry_count", 0))
    max_retries = int(state.get("max_retries", 3))

    result = apply_patch_and_run_tests(
        repo_owner=ctx.repo_owner,
        repo_name=ctx.repo_name,
        default_branch=ctx.default_branch,
        unified_diff=patch.unified_diff,
        tests_written=patch.tests_written,
        base_commit_sha=ctx.base_commit_sha or None,
    )

    tests_passed = int(result["test_exit_code"]) == 0
    lint_passed = int(result["lint_exit_code"]) == 0
    type_check_passed = int(result["type_check_exit_code"]) == 0

    if tests_passed and lint_passed and type_check_passed:
        routing = RoutingDecision.CONTINUE
    elif retry_count >= max_retries:
        routing = RoutingDecision.HUMAN_REVIEW
    else:
        routing = RoutingDecision.RETRY_PATCH

    output = ValidationOutput(
        test_exit_code=int(result["test_exit_code"]),
        tests_passed=tests_passed,
        lint_passed=lint_passed,
        type_check_passed=type_check_passed,
        stdout=str(result.get("stdout", "")),
        stderr=str(result.get("stderr", "")),
        retry_count=retry_count,
        routing_decision=routing,
    )

    logger.info(
        "node complete",
        extra={
            "output_payload": {
                "tests_passed": output.tests_passed,
                "lint_passed": output.lint_passed,
                "type_check_passed": output.type_check_passed,
                "test_exit_code": output.test_exit_code,
                "routing_decision": output.routing_decision.value,
            },
        },
    )
    return {"validation_output": output}
