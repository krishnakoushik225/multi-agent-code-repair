from __future__ import annotations

from enum import Enum
from typing import Any, List, Optional, TypeVar, TypedDict

from pydantic import BaseModel, Field

TModel = TypeVar("TModel", bound=BaseModel)


def as_model(model_cls: type[TModel], obj: Any) -> TModel:
    """Rehydrate Pydantic models after LangGraph checkpoint round-trips."""
    if isinstance(obj, model_cls):
        return obj
    if isinstance(obj, dict):
        return model_cls.model_validate(obj)
    raise TypeError(f"Expected {model_cls.__name__} or dict, got {type(obj)}")


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class RoutingDecision(str, Enum):
    CONTINUE = "continue"
    RETRY_PATCH = "retry_patch"
    HUMAN_REVIEW = "human_review"
    COMPLETE = "complete"


class IssueContext(BaseModel):
    issue_number: int
    title: str
    body: str
    labels: List[str]
    repo_owner: str
    repo_name: str
    repo_url: str
    default_branch: str
    base_commit_sha: str = Field(
        default="",
        description="Commit SHA pinned at ingestion; research + git apply clone this exact tree.",
    )


class ResearchOutput(BaseModel):
    relevant_files: List[str] = Field(
        description="Relative paths of files relevant to the issue",
    )
    file_contents: dict[str, str] = Field(description="Map of file path to content")
    related_symbols: List[str] = Field(
        description="Function/class names related to the issue",
    )
    issue_summary: str = Field(description="One-paragraph technical summary of what is broken")
    confidence_score: float = Field(ge=0.0, le=1.0)


class PlanningOutput(BaseModel):
    fix_strategy: str = Field(description="Plain English description of the fix approach")
    candidate_files: List[str] = Field(description="Files that will be modified")
    estimated_lines_changed: int
    risk_level: RiskLevel
    requires_new_tests: bool
    ambiguous: bool = Field(description="True if the fix strategy is uncertain")
    ambiguity_reason: Optional[str] = None


class PatchOutput(BaseModel):
    unified_diff: str = Field(description="Full unified diff of the proposed changes")
    files_modified: List[str]
    explanation: str = Field(description="Why this patch addresses the issue")
    tests_written: Optional[str] = Field(None, description="New test code if required")


class ValidationOutput(BaseModel):
    test_exit_code: int
    tests_passed: bool
    lint_passed: bool
    type_check_passed: bool
    stdout: str
    stderr: str
    retry_count: int
    routing_decision: RoutingDecision


class PROutput(BaseModel):
    pr_url: str
    pr_number: int
    title: str
    success: bool


class GraphState(TypedDict):
    issue_url: str
    dry_run: bool
    base_commit_sha_override: Optional[str]
    issue_context: Optional[IssueContext]
    research_output: Optional[ResearchOutput]
    planning_output: Optional[PlanningOutput]
    patch_output: Optional[PatchOutput]
    validation_output: Optional[ValidationOutput]
    pr_output: Optional[PROutput]
    retry_count: int
    max_retries: int
    error_message: Optional[str]
    final_status: Optional[str]
