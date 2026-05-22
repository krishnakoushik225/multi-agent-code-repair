from __future__ import annotations

from graph.state import IssueContext, PlanningOutput, ResearchOutput, RiskLevel
from prompts.patch_prompt import build_patch_prompt


def _ctx() -> IssueContext:
    return IssueContext(
        issue_number=42,
        title="Click help option broken",
        body="Help option does not work.",
        labels=[],
        repo_owner="pallets",
        repo_name="click",
        repo_url="https://github.com/pallets/click.git",
        default_branch="main",
        base_commit_sha="abc123",
    )


def _research() -> ResearchOutput:
    return ResearchOutput(
        relevant_files=["src/click/core.py"],
        file_contents={},
        related_symbols=["make_context", "BaseCommand"],
        issue_summary="The help_option_names parameter is not respected by BaseCommand.",
        confidence_score=0.9,
    )


def _planning() -> PlanningOutput:
    return PlanningOutput(
        fix_strategy="Patch BaseCommand.make_context to honour help_option_names.",
        candidate_files=["src/click/core.py"],
        estimated_lines_changed=5,
        risk_level=RiskLevel.LOW,
        requires_new_tests=True,
        ambiguous=False,
    )


def test_patch_prompt_includes_issue_summary() -> None:
    prompt = build_patch_prompt(_ctx(), _research(), _planning(), {})
    assert "help_option_names parameter is not respected" in prompt


def test_patch_prompt_includes_related_symbols() -> None:
    prompt = build_patch_prompt(_ctx(), _research(), _planning(), {})
    assert "make_context" in prompt
    assert "BaseCommand" in prompt


def test_patch_prompt_includes_prior_error_on_retry() -> None:
    prior = {"stderr": "search string not found in src/click/core.py", "stdout": "", "attempt": 1}
    prompt = build_patch_prompt(_ctx(), _research(), _planning(), {}, prior_error=prior)
    assert "PREVIOUS ATTEMPT FAILED" in prompt
    assert "search string not found" in prompt


def test_patch_prompt_no_prior_error_block_on_first_attempt() -> None:
    prompt = build_patch_prompt(_ctx(), _research(), _planning(), {})
    assert "PREVIOUS ATTEMPT FAILED" not in prompt


def test_patch_prompt_empty_symbols_handled() -> None:
    research = _research()
    research = research.model_copy(update={"related_symbols": []})
    prompt = build_patch_prompt(_ctx(), research, _planning(), {})
    assert "none identified" in prompt
