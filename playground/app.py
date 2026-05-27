"""web-auto-form Online Playground — Gradio app.

Paste a JSON config, click Run, see the results in real time.

Usage:
    pip install gradio
    python playground/app.py

Deploy to Hugging Face Spaces:
    - SDK: Gradio
    - App file: playground/app.py
    - requirements.txt includes: gradio, web-auto-form, playwright
"""

from __future__ import annotations

import json
import sys
import traceback
from pathlib import Path

# Allow running from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

import gradio as gr
from web_auto_form import run

# ── Preset Examples ─────────────────────────────────────────────────────────

PRESETS = {
    "Contact Form": {
        "url": "https://httpbin.org/forms/post",
        "consent_statement": "Playground demo: filling a test contact form.",
        "steps": [
            {"action": "fill", "selector": "input[name='custname']", "value": "Jane Doe"},
            {"action": "fill", "selector": "input[name='custemail']", "value": "jane@example.com"},
            {"action": "select", "selector": "select[name='custaddresstype']", "value": "business"},
            {"action": "click", "selector": "button[type='submit']"},
            {"action": "wait", "type": "navigation"},
        ],
    },
    "Login + Assertion": {
        "url": "https://the-internet.herokuapp.com/login",
        "consent_statement": "Playground demo: login to public test site.",
        "steps": [
            {"action": "fill", "selector": "#username", "value": "tomsmith"},
            {"action": "fill", "selector": "#password", "value": "SuperSecretPassword!"},
            {"action": "click", "selector": "button[type='submit']"},
            {"action": "wait", "type": "navigation"},
            {
                "action": "assert",
                "selector": ".flash.success",
                "state": "visible",
                "on_fail": "retry",
                "max_retries": 3,
            },
        ],
        "extract_schema": {
            "fields": [
                {"name": "flash_message", "selector": ".flash.success", "attribute": "text"}
            ]
        },
    },
    "Template Variables": {
        "url": "https://httpbin.org/forms/post",
        "consent_statement": "Playground demo: template variables.",
        "data": {
            "user": {"name": "Alice", "email": "alice@example.com", "phone": "555-0100"}
        },
        "steps": [
            {"action": "fill", "selector": "input[name='custname']", "value": "{{user.name}}"},
            {"action": "fill", "selector": "input[name='custemail']", "value": "{{user.email}}"},
            {"action": "fill", "selector": "input[name='custtel']", "value": "{{user.phone}}"},
            {"action": "click", "selector": "button[type='submit']"},
            {"action": "wait", "type": "navigation"},
        ],
    },
    "Conditional (if/else)": {
        "url": "https://httpbin.org/forms/post",
        "consent_statement": "Playground demo: conditional branching.",
        "steps": [
            {"action": "fill", "selector": "input[name='custname']", "value": "Conditional Test"},
            {
                "action": "if",
                "condition": {"selector": "input[name='custtel']", "state": "exist"},
                "then": [
                    {"action": "fill", "selector": "input[name='custtel']", "value": "555-0123"},
                ],
                "else": [
                    {
                        "action": "fill",
                        "selector": "input[name='custname']",
                        "value": "No phone field found",
                    },
                ],
            },
            {"action": "click", "selector": "button[type='submit']"},
            {"action": "wait", "type": "navigation"},
        ],
    },
}


# ── Build UI ────────────────────────────────────────────────────────────────


def build_presets() -> dict:
    """Build the preset label → JSON string mapping."""
    result = {}
    for label, config in PRESETS.items():
        result[label] = json.dumps(config, indent=2, ensure_ascii=False)
    return result


def run_config(config_json: str, headless: bool = True) -> tuple[str, str, str, str]:
    """Execute a web-auto-form config from JSON string."""
    if not config_json.strip():
        return "", "", "⚠️  Please paste a JSON config or select a preset.", ""

    # Parse
    try:
        config = json.loads(config_json)
    except json.JSONDecodeError as e:
        return "", "", f"❌ Invalid JSON: {e}", ""

    # Override headless
    config.setdefault("options", {})["headless"] = headless

    # Validate required fields
    missing = []
    for field in ("url", "consent_statement", "steps"):
        if field not in config:
            missing.append(field)
    if missing:
        return "", "", f"❌ Missing required fields: {', '.join(missing)}", ""

    # Execute
    try:
        result = run(config)
    except Exception as e:
        return "", "", f"❌ Execution error:\n\n```\n{traceback.format_exc()}\n```", ""

    # Format results
    status = result["status"]
    status_emoji = {"success": "✅", "partial": "⚠️", "failed": "❌"}.get(status, "❓")

    steps_text = "| Step | Action | Status | Duration |\n|------|--------|--------|----------|\n"
    for r in result.get("results", []):
        s = r["status"]
        mark = "✓" if s == "ok" else "✗"
        steps_text += f"| {r['step']} | {r['action']} | {mark} {s} | {r['duration_ms']}ms |\n"

    steps_text += f"\n**{status_emoji} Final Status: {status}**\n"
    steps_text += f"- Steps executed: {result.get('steps_executed', 0)}\n"
    steps_text += f"- Steps skipped: {result.get('steps_skipped', 0)}\n"
    steps_text += f"- Steps failed: {result.get('steps_failed', 0)}\n"

    # Extracted data
    extracted_str = ""
    if result.get("extracted"):
        extracted_str = "| Field | Value |\n|-------|-------|\n"
        for key, value in result["extracted"].items():
            extracted_str += f"| {key} | {value} |\n"
    else:
        extracted_str = "_No extraction schema configured._"

    # Errors
    error_str = ""
    if result.get("errors"):
        error_str = "\n".join(f"- {e}" for e in result["errors"])
    else:
        error_str = "_No errors._"

    # Raw output
    raw_output = json.dumps(result, indent=2, ensure_ascii=False)

    return steps_text, extracted_str, error_str, raw_output


# ── Gradio Interface ────────────────────────────────────────────────────────

PRESET_CHOICES = list(PRESETS.keys())
PRESET_MAP = build_presets()

CSS = """
#config-editor textarea {
    font-family: 'Cascadia Code', 'Fira Code', 'JetBrains Mono', monospace !important;
    font-size: 13px !important;
    line-height: 1.5 !important;
}
footer { visibility: hidden; }
"""


def on_preset_change(preset_name: str) -> str:
    """Update the editor when a preset is selected."""
    return PRESET_MAP.get(preset_name, "")


with gr.Blocks(
    title="web-auto-form Playground",
    theme=gr.themes.Soft(),
    css=CSS,
) as demo:
    gr.Markdown(
        """
# 🧪 web-auto-form Playground

**Paste a JSON config → Click Run → See results in a real browser.**

No installation. No setup. Just JSON.
"""
    )

    with gr.Row():
        with gr.Column(scale=2):
            gr.Markdown("### 📝 Config")
            preset_dropdown = gr.Dropdown(
                choices=PRESET_CHOICES,
                label="Load a preset example",
                value=None,
                interactive=True,
            )
            config_editor = gr.Code(
                value="",
                language="json",
                label="JSON Configuration",
                lines=20,
                elem_id="config-editor",
            )

            with gr.Row():
                run_btn = gr.Button("🚀 Run", variant="primary", size="lg")
                headless_checkbox = gr.Checkbox(
                    label="Headless mode", value=True
                )

        with gr.Column(scale=3):
            gr.Markdown("### 📊 Results")
            steps_output = gr.Markdown("_Click Run to execute..._")

            with gr.Tabs():
                with gr.Tab("Extracted Data"):
                    extracted_output = gr.Markdown("")
                with gr.Tab("Errors"):
                    errors_output = gr.Markdown("")
                with gr.Tab("Raw JSON"):
                    raw_output = gr.Code(
                        language="json",
                        label="Raw Result",
                        lines=15,
                    )

    # Preset → editor binding
    preset_dropdown.change(
        fn=on_preset_change,
        inputs=[preset_dropdown],
        outputs=[config_editor],
    )

    # Run button
    run_btn.click(
        fn=run_config,
        inputs=[config_editor, headless_checkbox],
        outputs=[steps_output, extracted_output, errors_output, raw_output],
    )

    gr.Markdown(
        """
---
💡 **Tip**: Check out the [examples](../examples/) directory for more config ideas.
Read the [docs](../docs/) for the full reference.
"""
    )

if __name__ == "__main__":
    demo.launch()
