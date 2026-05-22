from __future__ import annotations

from graph.state import (
    FileChange,
    IssueContext,
    PatchOutput,
    PlanningOutput,
    RiskLevel,
    RoutingDecision,
    ValidationOutput,
)
from tools.pr_template import build_pr_body, build_pr_title


def _ctx() -> IssueContext:
    return IssueContext(
        issue_number=42,
        title="Fix off-by-one in pager",
        body="details",
        labels=[],
        repo_owner="pallets",
        repo_name="click",
        repo_url="https://github.com/pallets/click/issues/42",
        default_branch="main",
        base_commit_sha="abc123",
    )


def _planning() -> PlanningOutput:
    return PlanningOutput(
        fix_strategy="Decrement loop counter by one",
        candidate_files=["src/click/utils.py"],
        estimated_lines_changed=3,
        risk_level=RiskLevel.LOW,
        requires_new_tests=False,
        ambiguous=False,
    )


def _patch() -> PatchOutput:
    return PatchOutput(
        file_changes=[
            FileChange(
                path="src/click/utils.py",
                search="i <= n",
                replace="i < n",
                description="Fix off-by-one in loop",
            )
        ],
        explanation="The loop ran one extra iteration.",
    )


def _validation(passed: bool = True) -> ValidationOutput:
    return ValidationOutput(
        test_exit_code=0 if passed else 1,
        tests_passed=passed,
        lint_passed=passed,
        type_check_passed=passed,
        stdout="",
        stderr="",
        retry_count=0,
        routing_decision=RoutingDecision.COMPLETE,
    )


def test_build_pr_title_contains_issue_number_and_title():
    title = build_pr_title(_ctx())
    assert "#42" in title
    assert "Fix off-by-one in pager" in title


def test_build_pr_title_starts_with_fix():
    assert build_pr_title(_ctx()).startswith("fix:")


def test_build_pr_body_contains_issue_number():
    body = build_pr_body(_ctx(), _planning(), _patch(), _validation())
    assert "#42" in body


def test_build_pr_body_lists_modified_file():
    body = build_pr_body(_ctx(), _planning(), _patch(), _validation())
    assert "src/click/utils.py" in body


def test_build_pr_body_shows_validation_passed():
    body = build_pr_body(_ctx(), _planning(), _patch(), _validation(passed=True))
    assert "Passed" in body


def test_build_pr_body_shows_validation_failed():
    body = build_pr_body(_ctx(), _planning(), _patch(), _validation(passed=False))
    assert "Failed" in body


def test_build_pr_body_closes_issue():
    body = build_pr_body(_ctx(), _planning(), _patch(), _validation())
    assert "Closes #42" in body
