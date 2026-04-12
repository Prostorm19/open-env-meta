---
title: Code Review OpenEnv
emoji: "🔍"
colorFrom: indigo
colorTo: purple
sdk: docker
app_port: 8000
pinned: false
tags:
  - openenv
  - code-review
  - security
---

# Code Review OpenEnv

An OpenEnv-compliant environment where an AI agent reviews pull request diffs and identifies real-world bugs, security vulnerabilities, and style issues — the same problems engineers catch in daily code review.

Built for the OpenEnv Hackathon by Meta & Hugging Face.

---

## What This Project Does

This project is a **benchmark environment** for training and evaluating AI agents on code review tasks. It does not review your code directly — instead, it simulates realistic pull requests with deliberately planted bugs and security vulnerabilities.

An AI agent interacts with the environment by:
1. Receiving a fake PR (title, description, file diffs)
2. Submitting `report_issue` actions pointing to where it thinks bugs are
3. Getting scored on accuracy, severity, category, description quality, and fix quality

This creates a reproducible, measurable benchmark for how well an AI agent can do code review.

---

## Why This Matters

Code review is one of the most impactful quality gates in software engineering. The ability to reliably detect SQL injection, weak cryptography, IDOR vulnerabilities, and race conditions in PR diffs has immediate practical value for the developer tooling ecosystem.

---

## Project Structure

```
openenv-code-review/
├── server/
│   ├── __init__.py
│   ├── app.py                      # FastAPI server (OpenEnv HTTP contract)
│   └── code_review_environment.py  # Core environment logic
├── tests/
│   ├── test_environment.py
│   └── test_graders.py
├── __init__.py
├── models.py          # Pydantic models (Action, Observation)
├── client.py          # EnvClient subclass
├── environment.py     # Standalone env (used by inference + tests)
├── graders.py         # Reward logic and episode scoring
├── tasks.py           # 5 deterministic task definitions
├── inference.py       # LLM agent runner
├── openenv.yaml       # OpenEnv spec metadata
├── pyproject.toml
├── Dockerfile
└── requirements.txt
```

---

## Tasks

| Task | Difficulty | Issues | Description |
|---|---|---|---|
| `easy` | Easy | 2 | PEP8 naming violation + unused variable |
| `medium` | Medium | 1 | Off-by-one pagination bug |
| `hard` | Hard | 2 | SQL injection + MD5 password hashing |
| `expert` | Expert | 2 | TOCTOU race condition across 2 files |
| `adversarial` | Adversarial | 2 | IDOR + missing rate limiting (PR description lies) |
| `jwt_bypass` | Hard | 2 | JWT alg:none attack + hardcoded secret |
| `path_traversal` | Medium | 1 | Directory traversal via unsanitized filename |
| `crypto_fail` | Hard | 2 | AES-ECB mode + hardcoded encryption key |
| `ssrf` | Expert | 1 | SSRF via removed domain allowlist |
| `deserialization` | Adversarial | 2 | Insecure pickle deserialization + command injection |

**10 tasks total across 5 difficulty levels.** Tasks marked Adversarial have PR descriptions that actively mislead the reviewer.

---

## Action Space

Two action types are supported:

**report_issue** — identify a bug or vulnerability:

| Field | Type | Description |
|---|---|---|
| action_type | `"report_issue"` | Action type |
| filename | string | File containing the issue |
| line_start | int (≥1) | Start line (1-indexed) |
| line_end | int (≥ line_start) | End line |
| severity | `info` \| `warning` \| `error` \| `critical` | Issue severity |
| category | `style` \| `logic` \| `security` \| `performance` \| `maintainability` | Issue type |
| description | string | Human-readable explanation |
| suggested_fix | string \| null | Corrected code snippet |
| confidence | float [0.0, 1.0] | Agent confidence |

**ask_question** — ask a clarifying question (costs one step):

| Field | Type | Description |
|---|---|---|
| action_type | `"ask_question"` | Action type |
| question | string | Clarifying question about the PR |
| confidence | float [0.0, 1.0] | Agent confidence |

**request_hint** — get a partial hint about an unfound issue (costs 2 steps):

| Field | Type | Description |
|---|---|---|
| action_type | `"request_hint"` | Action type |

The hint reveals the file, severity, and approximate line range of the highest-severity unfound issue.

---

## Reward Function

Per-step reward is shaped across five factors:

| Factor | Weight | Description |
|---|---|---|
| issue_detection | 0.30 | Line-range overlap with the planted issue |
| severity_accuracy | 0.20 | Correct severity label |
| category_accuracy | 0.20 | Correct category label |
| description_quality | 0.15 | Keyword coverage in the description |
| fix_quality | 0.10 | Fix hint token overlap in the suggested fix |

**Penalties:**
- False positive (flagging clean code): −0.15
- Re-submitting an already-found issue: reward × 0.15

**Episode-level final score:**
- Severity-weighted recall (0.60) — missing a `critical` costs 3× missing a `warning`
- Precision (0.25) — each false positive reduces score by 0.15
- Fix rate (0.15) — fraction of found issues with a valid fix

---

## Baseline Scores

Deterministic fallback agent (no LLM required), average reward per step:

| Task | Difficulty | Avg Reward |
|---|---|---|
| easy | Easy | ~0.95 |
| medium | Medium | ~0.95 |
| path_traversal | Medium | ~0.91 |
| jwt_bypass | Hard | ~0.85 |
| hard | Hard | ~0.85 |
| crypto_fail | Hard | ~0.82 |
| expert | Expert | ~0.88 |
| ssrf | Expert | ~0.88 |
| adversarial | Adversarial | ~0.87 |
| deserialization | Adversarial | ~0.87 |
| **average** | — | **~0.88** |

---

## Setup and Running Locally

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Run the API server

**Linux / macOS:**
```bash
HF_TOKEN=local uvicorn server.app:app --host 0.0.0.0 --port 8000
```

**Windows PowerShell:**
```powershell
$env:HF_TOKEN="local"; uvicorn server.app:app --host 0.0.0.0 --port 8000
```

Using `HF_TOKEN=local` skips the LLM and uses the deterministic fallback — no credentials needed.

### 3. Verify it's running

```bash
curl http://localhost:8000/health
# Expected: {"status": "healthy"}
```

### 4. Run inference with a real LLM

```bash
export HF_TOKEN=hf_your_token_here
export API_BASE_URL=https://api-inference.huggingface.co/v1
export MODEL_NAME=meta-llama/Llama-3.1-8B-Instruct
python inference.py
```

### 5. Run the test suite

```bash
pip install pytest
pytest tests/ -v
# Expected: 36 passed
```

---

## API Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/health` | Health check |
| GET | `/metadata` | Environment info |
| GET | `/schema` | Action and observation JSON schemas |
| GET | `/state` | Current environment state |
| GET | `/tasks` | List all tasks with difficulty metadata |
| GET | `/leaderboard` | Per-task difficulty weights and baseline scores |
| POST | `/reset` | Reset episode. Body: `{"task_id": "easy"}` |
| POST | `/step` | Submit action. Body: `{"action": {...}}` |

### Example: Reset to a task

```bash
curl -X POST http://localhost:8000/reset \
  -H "Content-Type: application/json" \
  -d '{"task_id": "hard"}'
```

### Example: Submit an issue report

```bash
curl -X POST http://localhost:8000/step \
  -H "Content-Type: application/json" \
  -d '{
    "action": {
      "action_type": "report_issue",
      "filename": "auth.py",
      "line_start": 9,
      "line_end": 10,
      "severity": "critical",
      "category": "security",
      "description": "SQL injection via f-string interpolation of username",
      "suggested_fix": "cursor.execute(\"... WHERE username = ?\", (username,))",
      "confidence": 0.97
    }
  }'
```

**Windows PowerShell:**
```powershell
Invoke-RestMethod -Method POST http://localhost:8000/reset `
  -ContentType "application/json" `
  -Body '{"task_id": "hard"}'

Invoke-RestMethod -Method POST http://localhost:8000/step `
  -ContentType "application/json" `
  -Body '{"action": {"action_type": "report_issue", "filename": "auth.py", "line_start": 9, "line_end": 10, "severity": "critical", "category": "security", "description": "SQL injection via f-string", "suggested_fix": "Use parameterized query", "confidence": 0.97}}' | ConvertTo-Json -Depth 10
```

---

## Docker

```bash
docker build -t code-review-openenv .
docker run -e HF_TOKEN=local -p 8000:8000 code-review-openenv
```

---

## Deploy to Hugging Face Spaces

### Step 1 — Initialize git (inside the project folder)

```bash
cd openenv-code-review
git init
git add .
git commit -m "Code Review OpenEnv - hackathon submission"
```

### Step 2 — Create a new Space on huggingface.co

- Go to: https://huggingface.co/new-space
- Space name: `code-review-openenv`
- SDK: **Docker**
- Visibility: **Public**
- Click **Create Space**

### Step 3 — Push

```bash
git remote add space https://huggingface.co/spaces/YOUR_USERNAME/code-review-openenv
git push space main
```

### Step 4 — Set Space secrets

Go to your Space → **Settings → Variables and secrets** → add:

| Name | Value |
|---|---|
| `HF_TOKEN` | your Hugging Face token |
| `API_BASE_URL` | `https://api-inference.huggingface.co/v1` |
| `MODEL_NAME` | `meta-llama/Llama-3.1-8B-Instruct` |

### Step 5 — Confirm it's running

```bash
curl https://YOUR_USERNAME-code-review-openenv.hf.space/health
# Expected: {"status": "healthy"}
```

---

## Environment Variables

| Variable | Default | Required |
|---|---|---|
| `HF_TOKEN` | — | Yes (use `local` for no-LLM mode) |
| `API_BASE_URL` | `https://api.openai.com/v1` | No |
| `MODEL_NAME` | `gpt-4.1-mini` | No |
