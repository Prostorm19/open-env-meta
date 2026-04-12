"""Gradio web UI for the Code Review OpenEnv environment."""

from __future__ import annotations
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import gradio as gr
import httpx
import json

BASE_URL = "http://localhost:8000"

TASKS = [
    "easy", "medium", "hard", "expert", "adversarial",
    "jwt_bypass", "path_traversal", "crypto_fail", "ssrf", "deserialization"
]

TASK_DESCRIPTIONS = {
    "easy":            "🟢 Easy — PEP8 naming + unused variable",
    "medium":          "🟡 Medium — Off-by-one pagination bug",
    "hard":            "🟠 Hard — SQL injection + MD5 hashing",
    "expert":          "🔴 Expert — TOCTOU race condition (multi-file)",
    "adversarial":     "💀 Adversarial — IDOR + rate limit (PR lies!)",
    "jwt_bypass":      "🟠 Hard — JWT alg:none attack + hardcoded secret",
    "path_traversal":  "🟡 Medium — Directory traversal via query param",
    "crypto_fail":     "🟠 Hard — AES-ECB mode + hardcoded key",
    "ssrf":            "🔴 Expert — SSRF via removed domain allowlist",
    "deserialization": "💀 Adversarial — Pickle RCE + command injection",
}


def reset_task(task_id: str):
    try:
        r = httpx.post(f"{BASE_URL}/reset", json={"task_id": task_id}, timeout=10)
        data = r.json()
        obs = data.get("observation", {})

        pr_info = f"**{obs.get('pr_title', '')}**\n\n{obs.get('pr_description', '')}"

        files_md = ""
        for f in obs.get("files", []):
            files_md += f"\n### 📄 `{f['filename']}`\n```diff\n{f['diff']}\n```\n"

        status = f"✅ Reset to **{task_id}** | Steps: 0/{obs.get('max_steps', '?')} | Issues found: 0"
        return pr_info, files_md, status, "[]", "[]", ""
    except Exception as e:
        return f"Error: {e}", "", "❌ Connection error", "[]", "[]", ""


def submit_report(task_id, filename, line_start, line_end, severity, category, description, suggested_fix, confidence):
    try:
        action = {
            "action_type": "report_issue",
            "filename": filename,
            "line_start": int(line_start),
            "line_end": int(line_end),
            "severity": severity,
            "category": category,
            "description": description,
            "suggested_fix": suggested_fix if suggested_fix.strip() else None,
            "confidence": float(confidence),
        }
        r = httpx.post(f"{BASE_URL}/step", json={"action": action}, timeout=10)
        data = r.json()
        obs = data.get("observation", {})
        reward = data.get("reward") or 0
        done = data.get("done", False)

        feedback = obs.get("last_feedback", "")
        issues_found = json.dumps(obs.get("issues_found", []), indent=2)
        fixes_submitted = json.dumps(obs.get("fixes_submitted", []), indent=2)

        emoji = "✅" if reward > 0.7 else ("⚠️" if reward > 0 else "❌")
        status = (
            f"{emoji} Reward: **{reward:.3f}** | "
            f"Step: {obs.get('current_step', '?')}/{obs.get('max_steps', '?')} | "
            f"Issues found: {len(obs.get('issues_found', []))} | "
            f"{'🏁 DONE' if done else 'In progress'}"
        )
        return status, issues_found, fixes_submitted, feedback
    except Exception as e:
        return f"❌ Error: {e}", "[]", "[]", ""


def ask_question(task_id, question, confidence):
    try:
        action = {"action_type": "ask_question", "question": question, "confidence": float(confidence)}
        r = httpx.post(f"{BASE_URL}/step", json={"action": action}, timeout=10)
        data = r.json()
        obs = data.get("observation", {})
        clarifications = obs.get("clarifications", [])
        qa_text = "\n\n".join([f"**Q:** {c['question']}\n**A:** {c['answer']}" for c in clarifications])
        return qa_text or "No clarifications yet."
    except Exception as e:
        return f"❌ Error: {e}"


def request_hint(task_id):
    try:
        action = {"action_type": "request_hint", "confidence": 0.5}
        r = httpx.post(f"{BASE_URL}/step", json={"action": action}, timeout=10)
        data = r.json()
        obs = data.get("observation", {})
        feedback = obs.get("last_feedback", "No hint available.")
        step = obs.get("current_step", "?")
        max_steps = obs.get("max_steps", "?")
        return f"💡 {feedback}\n\n⚠️ Hint costs 2 steps. Now at step {step}/{max_steps}."
    except Exception as e:
        return f"❌ Error: {e}"


def build_ui():
    with gr.Blocks(title="Code Review OpenEnv") as demo:
        gr.Markdown("""
# 🔍 Code Review OpenEnv
**An OpenEnv benchmark where an AI agent reviews pull request diffs and identifies real-world security vulnerabilities.**

Built for the [OpenEnv Hackathon](https://huggingface.co/openenv) by Meta & Hugging Face.
        """)

        with gr.Row():
            with gr.Column(scale=1):
                gr.Markdown("### 🎯 Select Task")
                task_dropdown = gr.Dropdown(
                    choices=[(TASK_DESCRIPTIONS[t], t) for t in TASKS],
                    value="easy",
                    label="Task",
                    interactive=True,
                )
                reset_btn = gr.Button("🔄 Reset / Start Task", variant="primary")
                status_box = gr.Markdown("Click **Reset** to start.")

            with gr.Column(scale=2):
                gr.Markdown("### 📋 Pull Request")
                pr_info = gr.Markdown("Select a task and click Reset.")

        with gr.Row():
            with gr.Column():
                gr.Markdown("### 📝 Diff")
                diff_view = gr.Markdown(elem_classes=["diff-box"])

        gr.Markdown("---")
        gr.Markdown("### 🚨 Report an Issue")

        with gr.Row():
            with gr.Column():
                filename_input = gr.Textbox(label="Filename", placeholder="e.g. auth.py")
                with gr.Row():
                    line_start_input = gr.Number(label="Line Start", value=1, minimum=1)
                    line_end_input = gr.Number(label="Line End", value=1, minimum=1)
                with gr.Row():
                    severity_input = gr.Dropdown(
                        choices=["info", "warning", "error", "critical"],
                        value="warning", label="Severity"
                    )
                    category_input = gr.Dropdown(
                        choices=["style", "logic", "security", "performance", "maintainability"],
                        value="security", label="Category"
                    )
            with gr.Column():
                description_input = gr.Textbox(
                    label="Description", lines=3,
                    placeholder="Describe the issue clearly..."
                )
                fix_input = gr.Textbox(
                    label="Suggested Fix (optional)", lines=2,
                    placeholder="How to fix it..."
                )
                confidence_input = gr.Slider(0.0, 1.0, value=0.8, step=0.05, label="Confidence")

        submit_btn = gr.Button("📤 Submit Issue Report", variant="primary")

        with gr.Row():
            issues_found_box = gr.Code(label="✅ Issues Found", language="json", lines=4)
            fixes_box = gr.Code(label="🔧 Fixes Submitted", language="json", lines=4)

        feedback_box = gr.Markdown("**Feedback:** —")

        gr.Markdown("---")

        with gr.Row():
            with gr.Column():
                gr.Markdown("### ❓ Ask a Clarifying Question")
                question_input = gr.Textbox(label="Question", placeholder="e.g. Is this endpoint public?")
                q_confidence = gr.Slider(0.0, 1.0, value=0.7, step=0.05, label="Confidence")
                ask_btn = gr.Button("💬 Ask Question")
                qa_output = gr.Markdown("No questions asked yet.")

            with gr.Column():
                gr.Markdown("### 💡 Request a Hint")
                gr.Markdown("*Costs 2 steps — reveals file, severity, and line range of an unfound issue.*")
                hint_btn = gr.Button("💡 Get Hint", variant="secondary")
                hint_output = gr.Markdown("")

        # Wire up events
        reset_btn.click(
            fn=reset_task,
            inputs=[task_dropdown],
            outputs=[pr_info, diff_view, status_box, issues_found_box, fixes_box, feedback_box]
        )

        submit_btn.click(
            fn=submit_report,
            inputs=[task_dropdown, filename_input, line_start_input, line_end_input,
                    severity_input, category_input, description_input, fix_input, confidence_input],
            outputs=[status_box, issues_found_box, fixes_box, feedback_box]
        )

        ask_btn.click(
            fn=ask_question,
            inputs=[task_dropdown, question_input, q_confidence],
            outputs=[qa_output]
        )

        hint_btn.click(
            fn=request_hint,
            inputs=[task_dropdown],
            outputs=[hint_output]
        )

    return demo


if __name__ == "__main__":
    demo = build_ui()
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        theme=gr.themes.Soft(),
    )
