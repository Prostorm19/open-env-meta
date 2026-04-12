"""Industry-level reward logic for the Code Review OpenEnv environment.

Reward is shaped across six factors per step:

  1. issue_detection      — line-range overlap with a planted issue        (0.30)
  2. severity_accuracy    — correct severity label                         (0.20)
  3. category_accuracy    — correct category label                         (0.20)
  4. description_quality  — keyword coverage in the description            (0.15)
  5. fix_quality          — fix hint token overlap in the suggested fix    (0.10)
  6. priority_bonus       — extra reward for finding critical issues first (0.05)

Episode-level score combines:
  - severity-weighted recall  (0.60) — missing a critical costs 3x a warning
  - precision                 (0.25) — false positives are penalized
  - fix_rate                  (0.15) — fraction of found issues with a valid fix
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from models import CodeReviewAction as Action, PlantedIssue

# Reward result container
from typing import NamedTuple

class Reward(NamedTuple):
    score: float
    breakdown: dict


LINE_TOLERANCE = 3

# Severity weights for recall calculation — missing critical hurts much more
SEVERITY_WEIGHTS: Dict[str, float] = {
    "critical": 3.0,
    "error": 2.0,
    "warning": 1.0,
    "info": 0.5,
}

CATEGORY_KEYWORDS: Dict[str, List[str]] = {
    "style": ["pep8", "naming", "convention", "snake_case", "camelcase", "style", "format"],
    "logic": ["off-by-one", "off by one", "index", "pagination", "page", "skip", "wrong", "incorrect", "bug", "loop"],
    "security": [
        "injection", "sql", "md5", "hash", "password", "parameterized",
        "vulnerable", "attack", "broken", "idor", "ownership", "race",
        "toctou", "symlink", "traversal", "rate limit", "brute force",
        "enumeration", "authentication", "authorization",
    ],
    "performance": ["slow", "performance", "complexity", "loop", "cache", "optimize", "n+1"],
    "maintainability": ["unused", "dead code", "variable", "remove", "clean", "duplicate"],
}


# ─────────────────────────────────────────────────────────────────────────────
# Per-step grading helpers
# ─────────────────────────────────────────────────────────────────────────────

def _lines_overlap(
    agent_start: int,
    agent_end: int,
    truth_start: int,
    truth_end: int,
    tolerance: int = LINE_TOLERANCE,
) -> float:
    if agent_start == truth_start and agent_end == truth_end:
        return 1.0
    start_ok = abs(agent_start - truth_start) <= tolerance
    end_ok = abs(agent_end - truth_end) <= tolerance
    if start_ok and end_ok:
        return 0.7
    if start_ok or end_ok:
        return 0.4
    overlap_start = max(agent_start, truth_start)
    overlap_end = min(agent_end, truth_end)
    if overlap_start <= overlap_end:
        overlap_len = overlap_end - overlap_start + 1
        truth_len = truth_end - truth_start + 1
        return 0.2 * min(1.0, overlap_len / truth_len)
    return 0.0


def _description_quality(description: str, category: str) -> float:
    desc_lower = description.lower()
    keywords = CATEGORY_KEYWORDS.get(category, [])
    if not keywords:
        return 0.5
    hits = sum(1 for kw in keywords if kw in desc_lower)
    return min(1.0, hits / max(1, len(keywords) * 0.25))


def _fix_quality(suggested_fix: Optional[str], issue: PlantedIssue) -> float:
    if not suggested_fix:
        return 0.0
    fix_lower = suggested_fix.lower()
    hint_lower = issue.fix_hint.lower()
    hint_tokens = [t for t in hint_lower.split() if len(t) > 3]
    if not hint_tokens:
        return 0.5
    hits = sum(1 for token in hint_tokens if token in fix_lower)
    return min(1.0, hits / max(1, len(hint_tokens) * 0.35))


def _is_false_positive(action: Action, false_positive_targets: List[dict]) -> bool:
    """Return True if the action flags a known non-issue region."""
    for fp in false_positive_targets:
        if action.filename != fp["filename"]:
            continue
        overlap = _lines_overlap(
            action.line_start, action.line_end,
            fp["line_start"], fp["line_end"],
            tolerance=1,
        )
        if overlap >= 0.4:
            return True
    return False


def grade_action_against_issue(action: Action, issue: PlantedIssue) -> Dict[str, float]:
    breakdown: Dict[str, float] = {
        "issue_detection": 0.0,
        "severity_accuracy": 0.0,
        "category_accuracy": 0.0,
        "description_quality": 0.0,
        "fix_quality": 0.0,
    }
    if action.filename != issue.filename:
        return breakdown

    detection_score = _lines_overlap(
        action.line_start, action.line_end,
        issue.line_start, issue.line_end,
    )
    breakdown["issue_detection"] = detection_score

    if detection_score >= 0.2:
        breakdown["severity_accuracy"] = 1.0 if action.severity == issue.severity else 0.0
        breakdown["category_accuracy"] = 1.0 if action.category == issue.category else 0.0
        breakdown["description_quality"] = _description_quality(action.description or "", issue.category)
        breakdown["fix_quality"] = _fix_quality(action.suggested_fix, issue)

    return breakdown


def compute_reward(
    action: Action,
    planted_issues: List[PlantedIssue],
    already_found: List[str],
    false_positive_targets: Optional[List[dict]] = None,
    priority_issue_ids: Optional[List[str]] = None,
) -> Tuple[float, dict]:
    """
    Compute per-step reward.

    False positives (flagging known-clean code) return a negative reward.
    Re-finding an already-found issue is penalized.
    Finding a priority (critical) issue before lower-severity ones gives a bonus.
    """
    fp_targets = false_positive_targets or []
    priority_ids = set(priority_issue_ids or [])

    # False positive check — penalize immediately
    # Score must stay strictly within (0, 1) per Meta hackathon validator
    if _is_false_positive(action, fp_targets):
        return 0.01, {"matched_issue": None, "false_positive": True, "factors": {}}

    if not planted_issues:
        return 0.01, {}

    best_score = 0.0
    best_breakdown: Dict[str, float] = {}
    best_issue_id: Optional[str] = None

    weights = {
        "issue_detection": 0.30,
        "severity_accuracy": 0.20,
        "category_accuracy": 0.20,
        "description_quality": 0.15,
        "fix_quality": 0.10,
    }

    for issue in planted_issues:
        breakdown = grade_action_against_issue(action, issue)
        score = sum(breakdown[k] * weights[k] for k in weights)

        # Priority bonus: reward finding critical issues
        if issue.issue_id in priority_ids and breakdown["issue_detection"] >= 0.4:
            score = min(1.0, score + 0.05)

        if score > best_score:
            best_score = score
            best_breakdown = breakdown
            best_issue_id = issue.issue_id

    # Penalize re-finding an already-found issue
    if best_issue_id and best_issue_id in already_found:
        best_score *= 0.15
        best_breakdown = {k: v * 0.15 for k, v in best_breakdown.items()}

    # Clamp strictly within (0, 1) as required by Meta hackathon validator
    best_score = max(0.01, min(0.99, best_score))
    return best_score, {
        "matched_issue": best_issue_id,
        "factors": best_breakdown,
        "false_positive": False,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Episode-level scoring
# ─────────────────────────────────────────────────────────────────────────────

def episode_score(
    planted_issues: List[PlantedIssue],
    found_issue_ids: List[str],
    fix_issue_ids: List[str],
    false_positive_count: int = 0,
) -> Reward:
    """
    Compute the final episode-level reward.

    severity_weighted_recall (0.60):
        Each issue contributes weight proportional to its severity.
        Missing a critical issue costs 3x missing a warning.

    precision (0.25):
        Penalizes false positives. Each false positive reduces precision by 0.1,
        capped at 0.0.

    fix_rate (0.15):
        Fraction of planted issues for which a valid fix was submitted.
    """
    if not planted_issues:
        return Reward(score=0.01, breakdown={"recall": 0.0, "precision": 1.0, "fix_rate": 0.0})

    found_set = set(found_issue_ids)
    fixed_set = set(fix_issue_ids)
    issue_map = {i.issue_id: i for i in planted_issues}

    # Severity-weighted recall
    total_weight = sum(SEVERITY_WEIGHTS.get(i.severity, 1.0) for i in planted_issues)
    found_weight = sum(
        SEVERITY_WEIGHTS.get(issue_map[iid].severity, 1.0)
        for iid in found_set
        if iid in issue_map
    )
    recall = found_weight / total_weight if total_weight > 0 else 0.0

    # Precision — penalize false positives
    precision = max(0.0, 1.0 - false_positive_count * 0.15)

    # Fix rate
    fix_rate = len(fixed_set & set(issue_map)) / len(planted_issues)

    score = 0.60 * recall + 0.25 * precision + 0.15 * fix_rate
    # Clamp strictly within (0, 1) as required by Meta hackathon validator
    score = max(0.01, min(0.99, score))

    return Reward(
        score=round(score, 4),
        breakdown={
            "severity_weighted_recall": round(recall, 4),
            "precision": round(precision, 4),
            "fix_rate": round(fix_rate, 4),
            "issues_found": len(found_set & set(issue_map)),
            "issues_total": len(planted_issues),
            "false_positives": false_positive_count,
        },
    )
