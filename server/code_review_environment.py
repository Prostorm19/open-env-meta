"""Code Review Environment — core logic, decoupled from HTTP layer."""

from __future__ import annotations

import copy
import sys
import os

# Allow imports from project root when running inside server/ package
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from typing import Any, Dict, List, Optional, Tuple
from uuid import uuid4

from graders import compute_reward, episode_score
from models import (
    CodeFile, CodeReviewAction, CodeReviewObservation,
    ClarificationQA, PlantedIssue,
)
from tasks import get_canned_answer, get_task

try:
    from openenv.core.env_server.types import EnvironmentMetadata
except ImportError:
    EnvironmentMetadata = None


class CodeReviewEnvironment:
    """
    Stateful Code Review environment.

    Implements the OpenEnv interface:
        reset(**kwargs) → CodeReviewObservation
        step(action)    → CodeReviewObservation  (done/reward set on obs)
        state           → property returning current state dict
    """

    SUPPORTS_CONCURRENT_SESSIONS: bool = True

    def __init__(self) -> None:
        self._task_id: str = "easy"
        self._task: dict = {}
        self._planted_issues: List[PlantedIssue] = []
        self._files: List[CodeFile] = []
        self._false_positive_targets: List[dict] = []
        self._priority_issue_ids: List[str] = []
        self.max_steps: int = 5

        self._step_count: int = 0
        self._issues_found: List[str] = []
        self._fixes_submitted: List[str] = []
        self._false_positive_count: int = 0
        self._clarifications: List[ClarificationQA] = []
        self._last_feedback: Optional[str] = None
        self._done: bool = False
        self._episode_id: str = str(uuid4())

        self._load_task("easy")

    # ──────────────────────────────────────────────────────────────────────
    # OpenEnv interface
    # ──────────────────────────────────────────────────────────────────────

    def reset(
        self,
        task_id: str = "easy",
        episode_id: Optional[str] = None,
        seed: Optional[int] = None,
        **kwargs,
    ) -> CodeReviewObservation:
        """Reset episode and return initial observation."""
        self._load_task(task_id)
        self._step_count = 0
        self._issues_found = []
        self._fixes_submitted = []
        self._false_positive_count = 0
        self._clarifications = []
        self._last_feedback = None
        self._done = False
        self._episode_id = episode_id or str(uuid4())
        return self._make_obs()

    def step(self, action: CodeReviewAction) -> CodeReviewObservation:
        """Apply action and return observation with reward/done set."""
        if self._done:
            obs = self._make_obs()
            obs.done = True
            obs.reward = 1e-6
            return obs

        if action.action_type == "ask_question":
            reward = self._handle_question(action)
        elif action.action_type == "request_hint":
            reward = self._handle_hint(action)
        else:
            reward = self._handle_report(action)

        self._step_count += 1
        all_found = set(self._issues_found) >= {i.issue_id for i in self._planted_issues}
        self._done = all_found or self._step_count >= self.max_steps

        obs = self._make_obs()
        obs.done = self._done
        obs.reward = reward
        return obs

    @property
    def state(self) -> Dict[str, Any]:
        """Return current state as a plain dict (for /state endpoint)."""
        return {
            "episode_id": self._episode_id,
            "step_count": self._step_count,
            "task_id": self._task_id,
            "issues_found": list(self._issues_found),
            "fixes_submitted": list(self._fixes_submitted),
            "false_positive_count": self._false_positive_count,
            "done": self._done,
        }

    # ──────────────────────────────────────────────────────────────────────
    # Internal helpers
    # ──────────────────────────────────────────────────────────────────────

    def _load_task(self, task_id: str) -> None:
        try:
            self._task_id = task_id
            self._task = get_task(task_id)
        except KeyError as e:
            raise ValueError(str(e))
        self._planted_issues = [PlantedIssue(**i) for i in self._task["planted_issues"]]
        self._files = [CodeFile(**f) for f in self._task["files"]]
        self._false_positive_targets = self._task.get("false_positive_targets", [])
        self._priority_issue_ids = self._task.get("priority_issue_ids", [])
        self.max_steps = int(self._task["max_steps"])

    def _make_obs(self) -> CodeReviewObservation:
        obs = CodeReviewObservation(
            task_id=self._task_id,
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
            reward=None,
        )
        return obs

    def _handle_question(self, action: CodeReviewAction) -> float:
        answer = get_canned_answer(self._task_id, action.question or "")
        self._clarifications.append(
            ClarificationQA(question=action.question or "", answer=answer)
        )
        self._last_feedback = f"Q: {action.question} → A: {answer}"
        return 1e-6

    def _handle_hint(self, action: CodeReviewAction) -> float:
        """Request a hint — costs 2 steps worth of reward budget, reveals file+severity of an unfound issue."""
        unfound = [i for i in self._planted_issues if i.issue_id not in self._issues_found]
        if not unfound:
            self._last_feedback = "No more issues to hint at — you've found them all."
            return 1e-6
        # Give a hint about the highest-severity unfound issue
        from graders import SEVERITY_WEIGHTS
        target = max(unfound, key=lambda i: SEVERITY_WEIGHTS.get(i.severity, 1.0))
        hint = (
            f"Hint: There is a {target.severity} {target.category} issue "
            f"in '{target.filename}' around lines {target.line_start}–{target.line_end}."
        )
        self._clarifications.append(ClarificationQA(question="[hint requested]", answer=hint))
        self._last_feedback = hint
        # Costs 2 steps — advance step count by 1 extra
        self._step_count += 1
        return 1e-6

    def _handle_report(self, action: CodeReviewAction) -> float:
        reward, breakdown = compute_reward(
            action=action,
            planted_issues=self._planted_issues,
            already_found=self._issues_found,
            false_positive_targets=self._false_positive_targets,
            priority_issue_ids=self._priority_issue_ids,
        )

        if breakdown.get("false_positive"):
            self._false_positive_count += 1
            self._last_feedback = (
                f"False positive at {action.filename}:{action.line_start}-{action.line_end}. "
                f"Penalty: {reward:.3f}"
            )
            return reward

        matched_id = breakdown.get("matched_issue")
        factors = breakdown.get("factors", {})
        detection_score = factors.get("issue_detection", 0.0)

        if matched_id and detection_score >= 0.4 and matched_id not in self._issues_found:
            self._issues_found.append(matched_id)
            if action.suggested_fix and factors.get("fix_quality", 0.0) >= 0.3:
                self._fixes_submitted.append(matched_id)

        matched = breakdown.get("matched_issue")
        if not matched or factors.get("issue_detection", 0.0) < 0.2:
            self._last_feedback = f"No match at {action.filename}:{action.line_start}-{action.line_end}. reward={reward:.3f}"
        else:
            parts = [f"Matched {matched} (reward={reward:.3f})."]
            if factors.get("severity_accuracy", 0) < 1.0:
                parts.append("Severity incorrect.")
            if factors.get("category_accuracy", 0) < 1.0:
                parts.append("Category incorrect.")
            if factors.get("fix_quality", 0) < 0.3:
                parts.append("Fix missing or insufficient.")
            self._last_feedback = " ".join(parts)

        return reward

    async def step_async(self, action: CodeReviewAction) -> CodeReviewObservation:
        """Async version of step for openenv.core compatibility."""
        return self.step(action)

    async def reset_async(
        self,
        task_id: str = "easy",
        episode_id: Optional[str] = None,
        seed: Optional[int] = None,
        **kwargs,
    ) -> CodeReviewObservation:
        """Async version of reset for openenv.core compatibility."""
        from fastapi import HTTPException
        try:
            return self.reset(task_id=task_id, episode_id=episode_id, seed=seed, **kwargs)
        except (ValueError, KeyError) as e:
            raise HTTPException(status_code=400, detail=str(e))

    def close(self) -> None:
        """Cleanup method required by openenv.core."""
        pass

    def get_metadata(self):
        """Return environment metadata for openenv.core /metadata endpoint."""
        readme = ""
        try:
            readme_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "README.md")
            with open(readme_path, "r", encoding="utf-8") as f:
                readme = f.read()
        except Exception:
            pass

        meta = {
            "name": "Code Review OpenEnv",
            "description": (
                "An OpenEnv environment where an AI agent reviews pull request diffs "
                "and identifies real-world bugs, security vulnerabilities, and style issues. "
                "Features 10 tasks across 5 difficulty levels including JWT bypass, SSRF, "
                "insecure deserialization, path traversal, and adversarial PRs that lie about their changes."
            ),
            "version": "1.0.0",
            "author": "openenv-code-review",
            "readme_content": readme,
            "documentation_url": None,
        }
        if EnvironmentMetadata is not None:
            return EnvironmentMetadata(**meta)
        return meta

    def final_score(self) -> float:
        return episode_score(
            planted_issues=self._planted_issues,
            found_issue_ids=self._issues_found,
            fix_issue_ids=self._fixes_submitted,
            false_positive_count=self._false_positive_count,
        ).score
