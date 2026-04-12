"""OpenEnv-compliant Code Review environment (standalone, used by inference.py and tests)."""

from __future__ import annotations

import copy
from typing import Any, Dict, List, Tuple

from graders import compute_reward, episode_score
from models import (
    CodeReviewAction as Action,
    CodeReviewObservation as Observation,
    CodeFile, ClarificationQA, PlantedIssue,
)
from tasks import get_canned_answer, get_task


class CodeReviewEnvironment:
    """
    Stateful environment — reset() / state() / step() interface.
    Used directly by inference.py and tests.
    The server/ package wraps this same logic for HTTP.
    """

    def __init__(self, task_id: str = "easy") -> None:
        self.task_id = task_id
        self._task = get_task(task_id)
        self._planted_issues: List[PlantedIssue] = [
            PlantedIssue(**i) for i in self._task["planted_issues"]
        ]
        self._files: List[CodeFile] = [CodeFile(**f) for f in self._task["files"]]
        self._false_positive_targets: List[dict] = self._task.get("false_positive_targets", [])
        self._priority_issue_ids: List[str] = self._task.get("priority_issue_ids", [])
        self.max_steps: int = int(self._task["max_steps"])

        self._step_count: int = 0
        self._issues_found: List[str] = []
        self._fixes_submitted: List[str] = []
        self._false_positive_count: int = 0
        self._clarifications: List[ClarificationQA] = []
        self._last_feedback: str | None = None
        self._done: bool = False

    # ── OpenEnv API ───────────────────────────────────────────────────────

    def reset(self) -> Observation:
        self._step_count = 0
        self._issues_found = []
        self._fixes_submitted = []
        self._false_positive_count = 0
        self._clarifications = []
        self._last_feedback = None
        self._done = False
        return self.state()

    def state(self) -> Observation:
        return Observation(
            task_id=self.task_id,
            pr_title=self._task["pr_title"],
            pr_description=self._task["pr_description"],
            files=copy.deepcopy(self._files),
            current_step=self._step_count,
            max_steps=self.max_steps,
            issues_found=list(self._issues_found),
            fixes_submitted=list(self._fixes_submitted),
            clarifications=list(self._clarifications),
            last_feedback=self._last_feedback,
            done=self._done,
        )

    def step(self, action: Action) -> Tuple[Observation, float, bool, Dict[str, Any]]:
        if self._done:
            return self.state(), 0.0, True, {"error": "Episode done. Call reset()."}

        if action.action_type == "ask_question":
            reward, breakdown = self._handle_question(action)
        else:
            reward, breakdown = self._handle_report(action)

        self._step_count += 1
        all_found = set(self._issues_found) >= {i.issue_id for i in self._planted_issues}
        self._done = all_found or self._step_count >= self.max_steps

        info = {
            "reward_breakdown": breakdown,
            "issues_found": list(self._issues_found),
            "fixes_submitted": list(self._fixes_submitted),
            "false_positive_count": self._false_positive_count,
            "total_planted": len(self._planted_issues),
            "step_count": self._step_count,
        }
        return self.state(), reward, self._done, info

    # ── Handlers ─────────────────────────────────────────────────────────

    def _handle_question(self, action: Action) -> Tuple[float, dict]:
        answer = get_canned_answer(self.task_id, action.question or "")
        self._clarifications.append(ClarificationQA(question=action.question or "", answer=answer))
        self._last_feedback = f"Q: {action.question} → A: {answer}"
        return 0.0, {"action_type": "ask_question", "answer": answer}

    def _handle_report(self, action: Action) -> Tuple[float, dict]:
        reward, breakdown = compute_reward(
            action=action,
            planted_issues=self._planted_issues,
            already_found=self._issues_found,
            false_positive_targets=self._false_positive_targets,
            priority_issue_ids=self._priority_issue_ids,
        )

        if breakdown.get("false_positive"):
            self._false_positive_count += 1
            self._last_feedback = f"False positive at {action.filename}:{action.line_start}. Penalty: {reward:.3f}"
            return reward, breakdown

        matched_id = breakdown.get("matched_issue")
        factors = breakdown.get("factors", {})
        detection_score = factors.get("issue_detection", 0.0)

        if matched_id and detection_score >= 0.4 and matched_id not in self._issues_found:
            self._issues_found.append(matched_id)
            if action.suggested_fix and factors.get("fix_quality", 0.0) >= 0.3:
                self._fixes_submitted.append(matched_id)

        if not matched_id or detection_score < 0.2:
            self._last_feedback = f"No match at {action.filename}:{action.line_start}. reward={reward:.3f}"
        else:
            parts = [f"Matched {matched_id} (reward={reward:.3f})."]
            if factors.get("severity_accuracy", 0) < 1.0:
                parts.append("Severity incorrect.")
            if factors.get("category_accuracy", 0) < 1.0:
                parts.append("Category incorrect.")
            if factors.get("fix_quality", 0) < 0.3:
                parts.append("Fix missing or insufficient.")
            self._last_feedback = " ".join(parts)

        return reward, breakdown

    def planted_issues(self) -> List[PlantedIssue]:
        return list(self._planted_issues)

    def final_score(self) -> float:
        return episode_score(
            planted_issues=self._planted_issues,
            found_issue_ids=self._issues_found,
            fix_issue_ids=self._fixes_submitted,
            false_positive_count=self._false_positive_count,
        ).score
