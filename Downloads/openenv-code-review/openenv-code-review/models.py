"""Data models for the Code Review OpenEnv environment.

Inherits from openenv.core.env_server.types.Action / Observation
exactly as the reference reasoning_gym_env does.
Falls back to standalone Pydantic base classes when openenv-core
is not installed (local dev / tests).
"""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, model_validator

# ── Try to import from openenv-core (available in Docker / HF Space) ─────────
try:
    from openenv.core.env_server.types import Action as _BaseAction
    from openenv.core.env_server.types import Observation as _BaseObservation
    _OPENENV_AVAILABLE = True
except ImportError:
    # Local dev fallback — mirrors the exact fields from openenv.core.env_server.types
    class _BaseAction(BaseModel):  # type: ignore[no-redef]
        model_config = ConfigDict(extra="forbid", validate_assignment=True, arbitrary_types_allowed=True)
        metadata: Dict[str, Any] = Field(default_factory=dict)

    class _BaseObservation(BaseModel):  # type: ignore[no-redef]
        model_config = ConfigDict(extra="forbid", validate_assignment=True, arbitrary_types_allowed=True)
        done: bool = Field(default=False)
        reward: Optional[float] = Field(default=None)
        metadata: Dict[str, Any] = Field(default_factory=dict)

    _OPENENV_AVAILABLE = False

# ── Type literals ─────────────────────────────────────────────────────────────
SeverityType = Literal["info", "warning", "error", "critical"]
CategoryType = Literal["style", "logic", "security", "performance", "maintainability"]
ActionType   = Literal["report_issue", "ask_question", "request_hint"]

# ── Domain models ─────────────────────────────────────────────────────────────

class CodeFile(BaseModel):
    model_config = ConfigDict(extra="forbid")
    filename: str
    language: str
    original: str
    modified: str
    diff: str


class PlantedIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")
    issue_id: str
    filename: str
    line_start: int
    line_end: int
    severity: SeverityType
    category: CategoryType
    description: str
    fix_hint: str


class ClarificationQA(BaseModel):
    model_config = ConfigDict(extra="forbid")
    question: str
    answer: str


# ── Environment Action ────────────────────────────────────────────────────────

class CodeReviewAction(_BaseAction):
    """Action for the Code Review environment.

    action_type == "report_issue" : identify a bug/vulnerability in the diff
    action_type == "ask_question" : ask a clarifying question (costs one step)
    """
    model_config = ConfigDict(extra="forbid", validate_assignment=True, arbitrary_types_allowed=True)

    action_type: ActionType = Field("report_issue")

    # report_issue fields
    filename:     Optional[str]          = None
    line_start:   Optional[int]          = Field(None, ge=1)
    line_end:     Optional[int]          = Field(None, ge=1)
    severity:     Optional[SeverityType] = None
    category:     Optional[CategoryType] = None
    description:  Optional[str]          = Field(None, min_length=5)
    suggested_fix: Optional[str]         = None
    confidence:   float                  = Field(0.5, ge=0.0, le=1.0)

    # ask_question fields
    question: Optional[str] = None

    @model_validator(mode="after")
    def _validate_by_type(self) -> "CodeReviewAction":
        if self.action_type == "report_issue":
            missing = [
                f for f in ("filename", "line_start", "line_end", "severity", "category", "description")
                if getattr(self, f) is None
            ]
            if missing:
                raise ValueError(f"report_issue requires: {missing}")
            if self.line_end < self.line_start:  # type: ignore[operator]
                raise ValueError("line_end must be >= line_start")
        elif self.action_type == "ask_question":
            if not self.question or not self.question.strip():
                raise ValueError("ask_question requires a non-empty question")
        # request_hint requires no extra fields
        return self


# ── Environment Observation ───────────────────────────────────────────────────

class CodeReviewObservation(_BaseObservation):
    """Observation from the Code Review environment."""
    model_config = ConfigDict(extra="forbid", validate_assignment=True, arbitrary_types_allowed=True)

    task_id:        str
    pr_title:       str
    pr_description: str
    files:          List[CodeFile]
    current_step:   int            = 0
    max_steps:      int            = 5
    issues_found:   List[str]      = Field(default_factory=list)
    fixes_submitted: List[str]     = Field(default_factory=list)
    clarifications: List[ClarificationQA] = Field(default_factory=list)
    last_feedback:  Optional[str]  = None
