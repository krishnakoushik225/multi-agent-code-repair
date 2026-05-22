from __future__ import annotations

from graph.state import IssueContext, ResearchOutput
from prompts.planning_prompt import build_planning_prompt
from prompts.research_prompt import build_research_prompt


def _ctx(labels: list[str] | None = None) -> IssueContext:
    return IssueContext(
        issue_number=5,
        title="Broken pager output",
        body="When piping output, pager fails.",
        labels=labels or [],
        repo_owner="pallets",
        repo_name="click",
        repo_url="https://github.com/pallets/click/issues/5",
        default_branch="main",
        base_commit_sha="abc",
    )


def _research(symbols: list[str] | None = None) -> ResearchOutput:
    return ResearchOutput(
        relevant_files=["src/click/utils.py", "src/click/core.py"],
        file_contents={"src/click/utils.py": "def pager():\n    pass\n"},
        related_symbols=symbols or ["pager", "echo"],
        issue_summary="The pager exits too early due to a loop bound error.",
        confidence_score=0.85,
    )


# ── research_prompt ──────────────────────────────────────────────────────────


def test_research_prompt_contains_repo():
    prompt = build_research_prompt(_ctx(), ["src/click/utils.py"])
    assert "pallets/click" in prompt


def test_research_prompt_contains_issue_number():
    prompt = build_research_prompt(_ctx(), [])
    assert "#5" in prompt


def test_research_prompt_contains_issue_title():
    prompt = build_research_prompt(_ctx(), [])
    assert "Broken pager output" in prompt


def test_research_prompt_contains_tree_path():
    prompt = build_research_prompt(_ctx(), ["src/click/utils.py", "src/click/core.py"])
    assert "src/click/utils.py" in prompt


def test_research_prompt_no_labels_shows_none():
    prompt = build_research_prompt(_ctx(labels=[]), [])
    assert "(none)" in prompt


def test_research_prompt_labels_shown():
    prompt = build_research_prompt(_ctx(labels=["bug", "pager"]), [])
    assert "bug" in prompt


def test_research_prompt_requests_json():
    prompt = build_research_prompt(_ctx(), [])
    assert "candidate_files" in prompt
    assert "confidence_score" in prompt


# ── planning_prompt ──────────────────────────────────────────────────────────


def test_planning_prompt_contains_issue_number():
    prompt = build_planning_prompt(_ctx(), _research())
    assert "#5" in prompt


def test_planning_prompt_contains_relevant_file():
    prompt = build_planning_prompt(_ctx(), _research())
    assert "src/click/utils.py" in prompt


def test_planning_prompt_contains_symbols():
    prompt = build_planning_prompt(_ctx(), _research(symbols=["pager", "echo"]))
    assert "pager" in prompt


def test_planning_prompt_contains_issue_summary():
    prompt = build_planning_prompt(_ctx(), _research())
    assert "loop bound error" in prompt


def test_planning_prompt_contains_code_excerpt():
    prompt = build_planning_prompt(_ctx(), _research())
    assert "def pager()" in prompt


def test_planning_prompt_requests_json_keys():
    prompt = build_planning_prompt(_ctx(), _research())
    for key in ("fix_strategy", "candidate_files", "risk_level", "requires_new_tests", "ambiguous"):
        assert key in prompt


def test_planning_prompt_empty_symbols_no_crash():
    prompt = build_planning_prompt(_ctx(), _research(symbols=[]))
    assert "fix_strategy" in prompt
