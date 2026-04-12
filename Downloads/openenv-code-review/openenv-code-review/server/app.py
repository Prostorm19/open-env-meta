"""FastAPI application for the Code Review OpenEnv environment.

Mirrors reasoning_gym_env/server/app.py exactly:
- Uses create_app() from openenv.core when available (Docker / HF Space)
- Falls back to a standalone FastAPI app for local dev

Port: 8000  (as required by openenv.yaml)
"""

from __future__ import annotations

import sys
import os

# Ensure project root is on the path for both Docker and local runs
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── Try openenv.core path (Docker / HF Space) ────────────────────────────────
try:
    from openenv.core.env_server.http_server import create_app

    try:
        from models import CodeReviewAction, CodeReviewObservation
    except ImportError:
        from ..models import CodeReviewAction, CodeReviewObservation

    from .code_review_environment import CodeReviewEnvironment

    _singleton_env = CodeReviewEnvironment()

    def _env_factory():
        return _singleton_env

    app = create_app(
        _env_factory,
        CodeReviewAction,
        CodeReviewObservation,
        env_name="code_review_env",
        max_concurrent_envs=4,
    )

    # Fix: openenv.core's 422 handler tries to JSON-serialize ValueError objects
    # which crashes. Override with a safe handler.
    from fastapi import Request as _Request
    from fastapi.responses import JSONResponse as _JSONResponse
    from fastapi.exceptions import RequestValidationError as _RVE
    from starlette.exceptions import HTTPException as _HTTPExc

    def _safe_serialize(obj):
        if isinstance(obj, dict):
            return {k: _safe_serialize(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [_safe_serialize(i) for i in obj]
        if isinstance(obj, (str, int, float, bool, type(None))):
            return obj
        return str(obj)

    @app.exception_handler(_HTTPExc)
    async def _http_exc_handler(_req: _Request, exc: _HTTPExc):
        return _JSONResponse(
            status_code=exc.status_code,
            content={"detail": _safe_serialize(exc.detail)},
        )

    @app.exception_handler(_RVE)
    async def _validation_handler(_req: _Request, exc: _RVE):
        return _JSONResponse(
            status_code=422,
            content={"detail": _safe_serialize(exc.errors())},
        )

    @app.exception_handler(Exception)
    async def _generic_handler(_req: _Request, exc: Exception):
        import traceback
        return _JSONResponse(
            status_code=500,
            content={"detail": traceback.format_exc()},
        )

    # Add extra endpoints not provided by openenv.core
    TASK_METADATA = {
        "easy":            {"difficulty": "easy",        "difficulty_weight": 1.0, "num_issues": 2, "baseline_score": 0.95},
        "medium":          {"difficulty": "medium",      "difficulty_weight": 1.5, "num_issues": 1, "baseline_score": 0.95},
        "hard":            {"difficulty": "hard",        "difficulty_weight": 2.0, "num_issues": 2, "baseline_score": 0.85},
        "expert":          {"difficulty": "expert",      "difficulty_weight": 2.5, "num_issues": 2, "baseline_score": 0.88},
        "adversarial":     {"difficulty": "adversarial", "difficulty_weight": 3.0, "num_issues": 2, "baseline_score": 0.87},
        "jwt_bypass":      {"difficulty": "hard",        "difficulty_weight": 2.0, "num_issues": 2, "baseline_score": 0.85},
        "path_traversal":  {"difficulty": "medium",      "difficulty_weight": 1.5, "num_issues": 1, "baseline_score": 0.90},
        "crypto_fail":     {"difficulty": "hard",        "difficulty_weight": 2.0, "num_issues": 2, "baseline_score": 0.85},
        "ssrf":            {"difficulty": "expert",      "difficulty_weight": 2.5, "num_issues": 1, "baseline_score": 0.88},
        "deserialization": {"difficulty": "adversarial", "difficulty_weight": 3.0, "num_issues": 2, "baseline_score": 0.85},
    }

    from fastapi import APIRouter as _APIRouter
    _router = _APIRouter()

    @_router.get("/tasks")
    def _list_tasks():
        return {"tasks": TASK_METADATA}

    @_router.get("/leaderboard")
    def _leaderboard():
        return {
            "leaderboard": {
                tid: {"difficulty": m["difficulty"], "difficulty_weight": m["difficulty_weight"],
                      "num_issues": m["num_issues"], "baseline_score": m["baseline_score"]}
                for tid, m in TASK_METADATA.items()
            },
            "note": "Run /reset + /step to get your agent's scores."
        }

    app.include_router(_router)

    # Mount Gradio UI at /web
    try:
        import gradio as gr
        from gradio.routes import mount_gradio_app
        from .gradio_ui import build_ui
        _demo = build_ui()
        app = mount_gradio_app(app, _demo, path="/web")
    except Exception as _e:
        import warnings
        warnings.warn(f"Gradio UI could not be mounted: {_e}")

# ── Standalone fallback (local dev without openenv-core) ─────────────────────
except ImportError:
    import asyncio
    import copy
    from typing import Any, Dict

    from fastapi import FastAPI, HTTPException, Request

    try:
        from models import CodeReviewAction, CodeReviewObservation
    except ImportError:
        from ..models import CodeReviewAction, CodeReviewObservation

    from .code_review_environment import CodeReviewEnvironment

    app = FastAPI(title="Code Review OpenEnv", version="1.0.0")
    _lock = asyncio.Lock()
    _envs: Dict[str, CodeReviewEnvironment] = {}

    TASK_METADATA = {
        "easy":            {"difficulty": "easy",        "difficulty_weight": 1.0, "num_issues": 2, "baseline_score": 0.95},
        "medium":          {"difficulty": "medium",      "difficulty_weight": 1.5, "num_issues": 1, "baseline_score": 0.95},
        "hard":            {"difficulty": "hard",        "difficulty_weight": 2.0, "num_issues": 2, "baseline_score": 0.85},
        "expert":          {"difficulty": "expert",      "difficulty_weight": 2.5, "num_issues": 2, "baseline_score": 0.88},
        "adversarial":     {"difficulty": "adversarial", "difficulty_weight": 3.0, "num_issues": 2, "baseline_score": 0.87},
        "jwt_bypass":      {"difficulty": "hard",        "difficulty_weight": 2.0, "num_issues": 2, "baseline_score": 0.85},
        "path_traversal":  {"difficulty": "medium",      "difficulty_weight": 1.5, "num_issues": 1, "baseline_score": 0.90},
        "crypto_fail":     {"difficulty": "hard",        "difficulty_weight": 2.0, "num_issues": 2, "baseline_score": 0.85},
        "ssrf":            {"difficulty": "expert",      "difficulty_weight": 2.5, "num_issues": 1, "baseline_score": 0.88},
        "deserialization": {"difficulty": "adversarial", "difficulty_weight": 3.0, "num_issues": 2, "baseline_score": 0.85},
    }

    def _serialize(obs) -> dict:
        return obs.model_dump(mode="json") if hasattr(obs, "model_dump") else obs.dict()

    def _get_or_create(task_id: str) -> CodeReviewEnvironment:
        if task_id not in _envs:
            env = CodeReviewEnvironment()
            env.reset(task_id=task_id)
            _envs[task_id] = env
        return _envs[task_id]

    @app.get("/health")
    def health():
        return {"status": "healthy", "service": "code-review-openenv"}

    @app.get("/")
    def root():
        return {
            "name": "Code Review OpenEnv",
            "version": "1.0.0",
            "tasks": list(TASK_METADATA.keys()),
            "total_tasks": len(TASK_METADATA),
        }

    @app.get("/tasks")
    def list_tasks():
        return {"tasks": TASK_METADATA}

    @app.get("/leaderboard")
    def leaderboard():
        scores = {}
        for tid, meta in TASK_METADATA.items():
            scores[tid] = {
                "difficulty": meta["difficulty"],
                "difficulty_weight": meta["difficulty_weight"],
                "num_issues": meta["num_issues"],
                "baseline_score": meta["baseline_score"],
            }
        return {"leaderboard": scores, "note": "Run /reset + /step to get your agent's scores."}

    @app.get("/schema")
    def schema():
        return {
            "action": CodeReviewAction.model_json_schema(),
            "observation": CodeReviewObservation.model_json_schema(),
        }

    @app.api_route("/reset", methods=["GET", "POST"])
    async def reset(request: Request, task_id: str = "easy"):
        payload: dict = {}
        if request.method == "POST":
            try:
                payload = await request.json()
            except Exception:
                payload = {}
        tid = payload.get("task_id", task_id)
        try:
            async with _lock:
                env = CodeReviewEnvironment()
                obs = env.reset(task_id=tid)
                _envs[tid] = env
            return {"observation": _serialize(obs), "reward": None, "done": False}
        except Exception as exc:
            import traceback
            raise HTTPException(status_code=500, detail=traceback.format_exc())

    @app.get("/state")
    async def state(task_id: str = "easy"):
        async with _lock:
            env = _get_or_create(task_id)
            s = env.state
        return s

    @app.post("/step")
    async def step(request: Request):
        try:
            payload = await request.json()
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid JSON")
        task_id = "easy"
        if "action" in payload and isinstance(payload["action"], dict):
            task_id = payload.get("task_id", "easy")
            action_data = payload["action"]
        else:
            action_data = payload
        try:
            action = CodeReviewAction(**action_data)
        except Exception as exc:
            raise HTTPException(status_code=422, detail=str(exc))
        async with _lock:
            env = _get_or_create(task_id)
            obs = env.step(action)
        return {"observation": _serialize(obs), "reward": obs.reward, "done": obs.done}


def main(host: str = "0.0.0.0", port: int = 8000) -> None:
    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
