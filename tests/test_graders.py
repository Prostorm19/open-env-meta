"""Tests for the grading and reward logic."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from graders import (
    _lines_overlap,
    _description_quality,
    _fix_quality,
    grade_action_against_issue,
    compute_reward,
    episode_score,
)
from models import CodeReviewAction as Action, PlantedIssue


def _make_issue(**kwargs) -> PlantedIssue:
    defaults = dict(
        issue_id="test-1",
        filename="test.py",
        line_start=5,
        line_end=5,
        severity="error",
        category="logic",
        description="test issue",
        fix_hint="fix the bug",
    )
    defaults.update(kwargs)
    return PlantedIssue(**defaults)


def _make_action(**kwargs) -> Action:
    defaults = dict(
        filename="test.py",
        line_start=5,
        line_end=5,
        severity="error",
        category="logic",
        description="off-by-one index bug in loop",
        suggested_fix="fix the bug here",
        confidence=0.9,
    )
    defaults.update(kwargs)
    return Action(**defaults)


class TestLinesOverlap:
    def test_exact_match(self):
        assert _lines_overlap(5, 5, 5, 5) == 1.0

    def test_within_tolerance(self):
        score = _lines_overlap(5, 5, 6, 6)
        assert score == 0.7

    def test_no_overlap(self):
        score = _lines_overlap(1, 2, 20, 25)
        assert score == 0.0

    def test_partial_overlap(self):
        score = _lines_overlap(3, 8, 5, 10)
        assert score > 0.0


class TestDescriptionQuality:
    def test_security_keywords(self):
        score = _description_quality("SQL injection vulnerability via f-string", "security")
        assert score > 0.0

    def test_empty_description(self):
        score = _description_quality("", "logic")
        assert score == 0.0

    def test_irrelevant_description(self):
        score = _description_quality("nothing relevant here", "security")
        assert score == 0.0


class TestFixQuality:
    def test_good_fix(self):
        issue = _make_issue(fix_hint="use parameterized query instead")
        score = _fix_quality("use parameterized query instead of f-string", issue)
        assert score > 0.3

    def test_no_fix(self):
        issue = _make_issue(fix_hint="fix the bug")
        assert _fix_quality(None, issue) == 0.0

    def test_empty_fix(self):
        issue = _make_issue(fix_hint="fix the bug")
        assert _fix_quality("", issue) == 0.0


class TestGradeAction:
    def test_perfect_action(self):
        issue = _make_issue()
        action = _make_action()
        breakdown = grade_action_against_issue(action, issue)
        assert breakdown["issue_detection"] == 1.0
        assert breakdown["severity_accuracy"] == 1.0
        assert breakdown["category_accuracy"] == 1.0

    def test_wrong_file(self):
        issue = _make_issue(filename="correct.py")
        action = _make_action(filename="wrong.py")
        breakdown = grade_action_against_issue(action, issue)
        assert all(v == 0.0 for v in breakdown.values())

    def test_wrong_severity(self):
        issue = _make_issue(severity="critical")
        action = _make_action(severity="info")
        breakdown = grade_action_against_issue(action, issue)
        assert breakdown["severity_accuracy"] == 0.0

    def test_wrong_category(self):
        issue = _make_issue(category="security")
        action = _make_action(category="style")
        breakdown = grade_action_against_issue(action, issue)
        assert breakdown["category_accuracy"] == 0.0


class TestComputeReward:
    def test_reward_in_range(self):
        issue = _make_issue()
        action = _make_action()
        score, _ = compute_reward(action, [issue], [])
        assert 0.0 < score < 1.0

    def test_already_found_penalty(self):
        issue = _make_issue()
        action = _make_action()
        score_fresh, _ = compute_reward(action, [issue], [])
        score_repeat, _ = compute_reward(action, [issue], ["test-1"])
        assert score_repeat < score_fresh

    def test_no_issues_returns_zero(self):
        action = _make_action()
        score, _ = compute_reward(action, [], [])
        assert 0.0 < score < 1.0


class TestEpisodeScore:
    def test_all_found_and_fixed(self):
        issues = [_make_issue(issue_id="a"), _make_issue(issue_id="b")]
        reward = episode_score(issues, ["a", "b"], ["a", "b"])
        assert 0.0 < reward.score < 1.0

    def test_none_found(self):
        issues = [_make_issue(issue_id="a")]
        reward = episode_score(issues, [], [])
        # precision=1.0 (no false positives) contributes 0.25 even with 0 recall
        assert reward.score == pytest.approx(0.25, abs=0.01)

    def test_partial_credit(self):
        issues = [_make_issue(issue_id="a"), _make_issue(issue_id="b")]
        reward = episode_score(issues, ["a"], [])
        assert 0.0 < reward.score < 1.0

    def test_score_in_range(self):
        issues = [_make_issue(issue_id=str(i)) for i in range(5)]
        found = [str(i) for i in range(3)]
        reward = episode_score(issues, found, found[:1])
        assert 0.0 < reward.score < 1.0
