"""Interactive demo: natural language → web-auto-form JSON config → browser execution.

Shows how an AI agent would use web-auto-form to fill out web forms.

Usage:
    python demo/demo_agent.py

The demo accepts a task description in natural language, shows the generated
JSON config, and optionally executes it in a real browser.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Allow running from project root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from web_auto_form import run

WELCOME = """
╔══════════════════════════════════════════════════════════╗
║        web-auto-form — AI Agent Integration Demo         ║
║                                                          ║
║  Describe what you want in natural language.              ║
║  web-auto-form will show the JSON config and execute it.  ║
╚══════════════════════════════════════════════════════════╝
"""

DEMO_TASKS = {
    "1": {
        "label": "Fill a contact form",
        "task": "Fill the contact form at https://httpbin.org/forms/post "
        "with name=Jane Doe, email=jane@example.com, "
        "choose 'Support' from the department dropdown, and submit.",
        "config": {
            "url": "https://httpbin.org/forms/post",
            "consent_statement": "Demo: filling contact form with test data.",
            "data": {
                "name": "Jane Doe",
                "email": "jane@example.com",
            },
            "steps": [
                {"action": "fill", "selector": "input[name='custname']", "value": "{{name}}"},
                {"action": "fill", "selector": "input[name='custemail']", "value": "{{email}}"},
                {
                    "action": "select",
                    "selector": "select[name='custaddresstype']",
                    "value": "business",
                },
                {"action": "click", "selector": "button[type='submit']"},
                {"action": "wait", "type": "navigation"},
            ],
        },
    },
    "2": {
        "label": "Login to a demo site",
        "task": "Login to https://the-internet.herokuapp.com/login "
        "with username=tomsmith and password=SuperSecretPassword!, "
        "then verify the success message appears.",
        "config": {
            "url": "https://the-internet.herokuapp.com/login",
            "consent_statement": "Demo: automated login to public test site.",
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
                    {"name": "success_message", "selector": ".flash.success", "attribute": "text"}
                ]
            },
        },
    },
    "3": {
        "label": "Conditional form with if/else",
        "task": "Go to a form at https://httpbin.org/forms/post, "
        "fill the name field. If there's a phone field, fill it with 555-0123. "
        "Always click submit at the end.",
        "config": {
            "url": "https://httpbin.org/forms/post",
            "consent_statement": "Demo: conditional form with test data.",
            "steps": [
                {
                    "action": "fill",
                    "selector": "input[name='custname']",
                    "value": "Conditional Test",
                },
                {
                    "action": "if",
                    "condition": {"selector": "input[name='custtel']", "state": "exist"},
                    "then": [
                        {
                            "action": "fill",
                            "selector": "input[name='custtel']",
                            "value": "555-0123",
                        },
                    ],
                },
                {"action": "click", "selector": "button[type='submit']"},
                {"action": "wait", "type": "navigation"},
            ],
        },
    },
}


def print_config(config: dict) -> None:
    """Pretty-print a web-auto-form config."""
    print("\n" + "─" * 60)
    print(json.dumps(config, indent=2, ensure_ascii=False))
    print("─" * 60)


def run_config(config: dict) -> None:
    """Execute a config and print results."""
    print("\nRunning web-auto-form...\n")

    result = run(config)

    for step_result in result.get("results", []):
        status_mark = "✓" if step_result["status"] == "ok" else "✗"
        desc = step_result.get("description", "")
        print(
            f"  {status_mark} Step {step_result['step']}: "
            f"{step_result['action']:<12} "
            f"{desc:<30} "
            f"({step_result['duration_ms']}ms)"
        )

    print(f"\nStatus: {result['status']}")
    print(f"Steps executed: {result['steps_executed']}")
    print(f"Steps skipped: {result['steps_skipped']}")
    print(f"Steps failed: {result['steps_failed']}")

    if result.get("extracted"):
        print(f"\nExtracted data:")
        for key, value in result["extracted"].items():
            print(f"  {key}: {value}")

    if result.get("errors"):
        print(f"\nErrors:")
        for error in result["errors"]:
            print(f"  - {error}")


def main() -> None:
    print(WELCOME)

    print("Choose a demo task (or enter 'c' for custom):\n")
    for key, task in DEMO_TASKS.items():
        print(f"  [{key}] {task['label']}")
        print(f"      {task['task'][:80]}...\n")

    choice = input("Choice [1]: ").strip() or "1"

    if choice in DEMO_TASKS:
        task = DEMO_TASKS[choice]
        print(f"\nTask: {task['task']}")
        print_config(task["config"])
    elif choice.lower() == "c":
        print("\nEnter your task description (or write JSON config directly):")
        print("(Press Enter twice to finish)\n")
        lines = []
        while True:
            line = input()
            if line == "" and lines and lines[-1] == "":
                break
            lines.append(line)
        user_input = "\n".join(lines).strip()

        # Try to parse as JSON first
        try:
            config = json.loads(user_input)
            print_config(config)
        except json.JSONDecodeError:
            print(f"\nTask description: {user_input}")
            print("\n(In a real AI agent, the LLM would generate a config from this.")
            print("For this demo, let's use the contact form example with your data.)")
            config = DEMO_TASKS["1"]["config"]
            print_config(config)
    else:
        print("Invalid choice. Running task 1.")
        task = DEMO_TASKS["1"]
        print_config(task["config"])
        config = task["config"]

    execute = input("\nExecute in browser? (y/n) [y]: ").strip().lower() or "y"
    if execute == "y":
        try:
            run_config(config)
        except Exception as e:
            print(f"\nExecution error: {e}")
            print("(This is expected if the target website is unreachable or changed.)")
    else:
        print("Skipping execution. You can run the config manually with:")
        print("  web_auto_form run <config.json>")


if __name__ == "__main__":
    main()
