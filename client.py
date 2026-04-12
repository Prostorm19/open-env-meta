"""Code Review Environment Client.

Mirrors the pattern from reasoning_gym_env/client.py.
Inherits from openenv.core.EnvClient when available.
"""

from __future__ import annotations

from typing import Dict

try:
    from openenv.core import EnvClient
    from openenv.core.client_types import StepResult
    from openenv.core.env_server.types import State
    _OPENENV_AVAILABLE = True
except ImportError:
    # Fallback stubs for local dev — not used at runtime in Docker
    from typing import Generic, TypeVar
    ActT = TypeVar("ActT")
    ObsT = TypeVar("ObsT")
    StateT = TypeVar("StateT")

    class StepResult:  # type: ignore[no-redef]
        def __init__(self, observation, reward, done):
            self.observation = observation
            self.reward = reward
            self.done = done

    class State:  # type: ignore[no-redef]
        def __init__(self, episode_id=None, step_count=0):
            self.episode_id = episode_id
            self.step_count = step_count

    class EnvClient:  # type: ignore[no-redef]
        def __init__(self, base_url: str = "http://localhost:8000"):
            self.base_url = base_url
        def reset(self, **kwargs): ...
        def step(self, action): ...
        def close(self): ...

    _OPENENV_AVAILABLE = False

from .models import CodeReviewAction, CodeReviewObservation


class CodeReviewEnv(EnvClient):  # type: ignore[misc]
    """Client for the Code Review Environment.

    Example::

        env = CodeReviewEnv(base_url="https://your-space.hf.space")
        result = env.reset(task_id="hard")
        print(result.observation.pr_title)

        result = env.step(CodeReviewAction(
            action_type="report_issue",
            filename="auth.py",
            line_start=9, line_end=10,
            severity="critical", category="security",
            description="SQL injection via f-string",
            suggested_fix="Use parameterized query",
            confidence=0.97,
        ))
        print(result.reward)
        env.close()
    """

    def _step_payload(self, action: CodeReviewAction) -> Dict:
        data = action.model_dump(mode="json", exclude_none=True)
        return data

    def _parse_result(self, payload: Dict) -> StepResult:
        obs_data = payload.get("observation", {})
        observation = CodeReviewObservation(**obs_data)
        return StepResult(
            observation=observation,
            reward=payload.get("reward"),
            done=payload.get("done", False),
        )

    def _parse_state(self, payload: Dict) -> State:
        return State(
            episode_id=payload.get("episode_id"),
            step_count=payload.get("step_count", 0),
        )
