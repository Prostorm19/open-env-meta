"""Tests for the Code Review environment."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

import pytest
from environment import CodeReviewEnvironment
from models import CodeReviewAction as Action


def _perfect_action_easy_1():
    return Action(
        filename="utils.py",
        line_start=1, line_end=1,
        severity="warning", category="style",
        description="Function name CalculateTotal violates PEP8 snake_case convention",
        suggested_fix="def calculate_total(items):",
        confidence=0.95,
    )


def _perfect_action_easy_2():
    return Action(
        filename="utils.py",
        line_start=3, line_end=3,
        severity="info", category="maintainability",
        description="Variable unused_var is assigned but never used. Remove it.",
        suggested_fix="# removed",
        confidence=0.90,
    )


class TestReset:
    def test_reset_returns_observation(self):
        env = CodeReviewEnvironment("easy")
        obs = env.reset()
        assert obs.task_id == "easy"
        assert obs.current_step == 0
        assert obs.issues_found == []
        assert obs.done is False

    def test_reset_clears_state(self):
        env = CodeReviewEnvironment("easy")
        env.reset()
        env.step(_perfect_action_easy_1())
        obs = env.reset()
        assert obs.current_step == 0
        assert obs.issues_found == []


class TestState:
    def test_state_does_not_mutate(self):
        env = CodeReviewEnvironment("easy")
        env.reset()
        s1 = env.state()
        s2 = env.state()
        assert s1.current_step == s2.current_step
        assert s1.issues_found == s2.issues_found


class TestStep:
    def test_perfect_action_gives_high_reward(self):
        env = CodeReviewEnvironment("easy")
        env.reset()
        _, reward, _, _ = env.step(_perfect_action_easy_1())
        assert reward >= 0.7

    def test_reward_in_range(self):
        env = CodeReviewEnvironment("easy")
        env.reset()
        for _ in range(3):
            _, reward, _, _ = env.step(_perfect_action_easy_1())
            assert 0.0 <= reward <= 1.0

    def test_wrong_file_gives_zero(self):
        env = CodeReviewEnvironment("easy")
        env.reset()
        action = Action(
            filename="wrong_file.py",
            line_start=1, line_end=1,
            severity="warning", category="style",
            description="some issue",
            confidence=0.5,
        )
        _, reward, _, _ = env.step(action)
        assert reward == 0.0

    def test_episode_ends_when_all_found(self):
        env = CodeReviewEnvironment("easy")
        env.reset()
        env.step(_perfect_action_easy_1())
        _, _, done, _ = env.step(_perfect_action_easy_2())
        assert done is True

    def test_episode_ends_at_max_steps(self):
        env = CodeReviewEnvironment("easy")
        env.reset()
        done = False
        for _ in range(env.max_steps):
            action = Action(
                filename="utils.py",
                line_start=99, line_end=99,
                severity="info", category="style",
                description="nothing",
                confidence=0.1,
            )
            _, _, done, _ = env.step(action)
        assert done is True

    def test_step_after_done_returns_zero_reward(self):
        env = CodeReviewEnvironment("easy")
        env.reset()
        for _ in range(env.max_steps):
            env.step(_perfect_action_easy_1())
        _, reward, done, info = env.step(_perfect_action_easy_1())
        assert done is True
        assert reward == 0.0


class TestTasks:
    @pytest.mark.parametrize("task_id", ["easy", "medium", "hard"])
    def test_all_tasks_load(self, task_id):
        env = CodeReviewEnvironment(task_id)
        obs = env.reset()
        assert obs.task_id == task_id
        assert len(obs.files) >= 1

    def test_unknown_task_raises(self):
        with pytest.raises(KeyError):
            CodeReviewEnvironment("nonexistent")


class TestFinalScore:
    def test_perfect_episode_scores_high(self):
        env = CodeReviewEnvironment("easy")
        env.reset()
        env.step(_perfect_action_easy_1())
        env.step(_perfect_action_easy_2())
        score = env.final_score()
        assert score >= 0.7

    def test_empty_episode_scores_zero(self):
        env = CodeReviewEnvironment("easy")
        env.reset()
        score = env.final_score()
        # precision=1.0 with no false positives contributes 0.25 even with 0 recall
        assert score == pytest.approx(0.25, abs=0.01)
