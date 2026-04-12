"""FastAPI server for the Code Review OpenEnv environment.

Endpoints
---------
GET  /           — health check
POST /reset      — reset episode, returns initial observation
GET  /state      — current observation
POST /step       — apply an action, returns (observation, reward, done, info)
GET  /tasks      — list available task IDs
"""

from __future__ import annotations

import asyncio
from typing import Any, Dict

from fastapi import FastAPI, HTTPException, Request

from environment import CodeReviewEnvironment
from models import Action


app = FastAPI(title="Code Review OpenEnv", version="1.0.0")

_lock = asyncio.Lock()
_envs: Dict[str, CodeReviewEnvironment] = {}


def _serialize(obj) -> Any:
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    if hasattr(obj, "dict"):
        return obj.dict()
    return obj


def _get_env(task_id: str) -> CodeReviewEnvironment:
    if task_id not in _envs:
        _envs[task_id] = CodeReviewEnvironment(task_id)
    return _envs[task_id]


@app.get("/")
def root() -> dict:
    return {
        "name": "Code Review OpenEnv",
        "version": "1.0.0",
        "status": "ok",
        "tasks": ["easy", "medium", "hard"],
        "endpoints": {
            "reset": "POST /reset  body: {task_id: str}",
            "state": "GET  /state?task_id=easy",
            "step":  "POST /step   body: Action JSON",
        },
    }


@app.get("/tasks")
def list_tasks() -> dict:
    return {
        "tasks": [
            {"id": "easy",        "difficulty": "easy",        "description": "Style violations + unused variable (2 issues)"},
            {"id": "medium",      "difficulty": "medium",      "description": "Off-by-one pagination bug (1 issue)"},
            {"id": "hard",        "difficulty": "hard",        "description": "SQL injection + weak password hashing (2 critical issues)"},
            {"id": "expert",      "difficulty": "expert",      "description": "TOCTOU race condition across multi-file upload handler (2 issues)"},
            {"id": "adversarial", "difficulty": "adversarial", "description": "IDOR + missing rate limiting disguised as a clean refactor (2 critical issues)"},
        ]
    }


@app.api_route("/reset", methods=["GET", "POST"])
async def reset(request: Request, task_id: str = "easy") -> dict:
    payload: dict = {}
    if request.method == "POST":
        try:
            payload = await request.json()
        except Exception:
            payload = {}

    tid = payload.get("task_id", task_id)
    async with _lock:
        env = CodeReviewEnvironment(tid)
        _envs[tid] = env
        obs = env.reset()

    return {
        "status": "reset",
        "task_id": tid,
        "observation": _serialize(obs),
    }


@app.get("/state")
async def state(task_id: str = "easy") -> dict:
    async with _lock:
        env = _get_env(task_id)
        obs = env.state()
    return {
        "status": "ok",
        "task_id": task_id,
        "observation": _serialize(obs),
    }


@app.post("/step")
async def step(request: Request) -> dict:
    try:
        payload = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    # Support both flat action and wrapped {"action": {...}, "task_id": ...}
    task_id = "easy"
    if "action" in payload and isinstance(payload["action"], dict):
        task_id = payload.get("task_id", "easy")
        payload = payload["action"]

    try:
        action = Action(**payload)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    async with _lock:
        env = _get_env(task_id)
        obs, reward, done, info = env.step(action)

    return {
        "observation": _serialize(obs),
        "reward": reward,
        "done": done,
        "info": info,
    }
