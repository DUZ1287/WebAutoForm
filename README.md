# web-auto-form

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/downloads/)

> **JSON-driven browser automation for form filling, submission, and data extraction.**
>
> Describe your workflow in JSON. No code. No scripts. Just config.

---

## Why web-auto-form?

Most browser automation tools force you to write code. **web-auto-form** is different — you describe *what* to do in a JSON file, and the engine handles *how*. It's built for one thing: filling out web forms, reliably and safely.

### When should you use what?

| Dimension | web-auto-form | Playwright | Selenium | Browser-Use |
| --- | --- | --- | --- | --- |
| **Approach** | JSON config | Write code | Write code | Natural language |
| **Learning curve** | None | Moderate | Steep | None |
| **Best for** | Batch form filling, data entry, registration automation, CI form testing, LLM agent tool | Modern web testing, complex single-page app scenarios | Legacy enterprise QA, cross-browser testing | One-off exploratory tasks, research scrapes |
| **AI agent integration** | **Native** — ships with JSON tool schema + system prompt | Requires custom wrapper | Requires custom wrapper | Built-in (but indirect) |
| **Determinism** | 100% deterministic | Deterministic | Deterministic | Non-deterministic (LLM decisions) |
| **Execution speed** | Fast (no LLM inference) | Fast | Moderate | Slow (LLM call per step) |
| **PII redaction** | **Built-in** — auto-masks emails, phones, IDs | Manual | Manual | Manual |
| **Conditional logic** | Declarative `if`/`else` in JSON | Code-driven | Code-driven | Prompt-driven |
| **Selector resilience** | Auto-detection + fallback chain | Manual | Manual | LLM-driven (unreliable) |
| **Debug artifacts** | Auto screenshots + HTML snapshots per step | Trace viewer | Screenshots (manual) | Limited |
| **Cost per run** | Free (local execution) | Free | Free | LLM API cost per step |
| **Example use case** | "Fill 500 job applications with different data" | "Test a React dashboard with WebSocket state" | "Automate an IE-only legacy intranet form" | "Find the cheapest flight on any airline site" |

**Rule of thumb:**
- If it's a **form** — use web-auto-form
- If it's a **test suite** — use Playwright
- If it's **IE11 on Windows 7** — use Selenium
- If it's a **one-off exploration** — use Browser-Use

---

## Features

| Feature | Description |
|---|---|
| **13 action types** | navigate, fill, select, check, click, upload, wait, scroll, extract, press_key, handle_dialog, if, assert |
| **Template variables** | `{{user.name}}` syntax with nested dot-notation from a `data` object |
| **Selector fallbacks** | Primary selector + backup chain — resilient to DOM changes |
| **Conditional branching** | `if`/`else` with state-based or value-based conditions, up to 3 levels deep |
| **Assertions** | Verify page state with configurable retry and abort/continue/retry |
| **PII redaction** | Auto-mask emails, phone numbers, Chinese 18-digit IDs, and SSNs |
| **Structured extraction** | Extract text, attributes, or HTML from multiple elements into a named dict |
| **Debug mode** | Per-step screenshots, HTML snapshots, and Playwright trace logs |
| **CLI + Python API** | `web_auto_form run` or `from web_auto_form import run` |
| **LLM tool integration** | Ships with a JSON tool schema and system prompt for AI agents (Claude, Cursor, etc.) |

---

## Quick Start

### Installation

```bash
pip install web-auto-form
playwright install chromium
```

### Your first automation

Create `my_form.json`:

```json
{
  "url": "https://example.com/apply",
  "consent_statement": "Automating personal data entry.",
  "steps": [
    {"action": "fill", "selector": "#name", "value": "Alice"},
    {"action": "fill", "selector": "#email", "value": "alice@example.com"},
    {"action": "click", "selector": "button[type='submit']"}
  ]
}
```

Run it:

```bash
web_auto_form run my_form.json
```

---

## CLI

```bash
# Basic run
web_auto_form run config.json

# Override data values from command line
web_auto_form run config.json --data user.name=Bob --data user.email=bob@test.com

# Force headed mode + debug output
web_auto_form run config.json --no-headless --debug

# Save output to file
web_auto_form run config.json --output result.json
```

---

## Python API

```python
from web_auto_form import run, run_from_path

# From a dict
result = run({
    "url": "https://example.com",
    "consent_statement": "Testing.",
    "steps": [{"action": "fill", "selector": "#name", "value": "Test"}],
})

# From a JSON file
result = run_from_path("config.json")

print(result["status"])       # "success" | "partial" | "failed"
print(result["extracted"])    # {"field_name": "extracted value", ...}
```

### Return value

```python
{
    "status": "success",           # success | partial | failed
    "consent_logged": "...",
    "steps_executed": 14,
    "steps_skipped": 1,
    "steps_failed": 0,
    "results": [
        {"step": 0, "action": "fill", "status": "ok", "duration_ms": 340}
    ],
    "extracted": {
        "confirmation_message": "Your application has been submitted."
    },
    "step_screenshots": [],
    "final_screenshot": None,
    "errors": []
}
```

---

## Configuration Reference

### Top-level fields

| Field | Type | Required | Description |
|---|---|---|---|
| `url` | string | Yes | Starting URL |
| `consent_statement` | string | Yes | Automation purpose declaration (logged + displayed in headed mode) |
| `steps` | StepConfig[] | Yes | Ordered list of actions (1–50) |
| `data` | dict | No | Template variables accessed via `{{key}}` |
| `extract_schema` | ExtractSchemaConfig | No | Post-execution extraction rules |
| `options` | OptionsConfig | No | Global execution settings |

### Global options

| Option | Default | Description |
|---|---|---|
| `headless` | `true` | Run browser in headless mode |
| `viewport_width` | `1280` | Browser viewport width |
| `viewport_height` | `800` | Browser viewport height |
| `step_delay_ms` | `500` | Delay between steps (min 100ms) |
| `max_retries` | `1` | Max retries for retryable errors |
| `redact_pii` | `true` | Auto-redact PII in logs and extracted output |
| `debug` | `false` | Save screenshots, HTML snapshots, and trace logs |
| `sandbox` | `true` | Browser sandbox mode |
| `keep_open` | `false` | Keep browser open after completion |

---

## Action Types

### Navigation & Interaction

| Action | Description | Required |
|---|---|---|
| `navigate` | Open a URL | `value` (URL) |
| `fill` | Type text into an input | `selector`, `value` |
| `click` | Click an element | `selector` |
| `select` | Select a dropdown option by label | `selector`, `value` |
| `check` | Check or uncheck a checkbox | `selector`, `value` ("true"/"false") |
| `upload` | Upload a file (local path, URL, or data URI) | `selector`, `value` |
| `press_key` | Press a keyboard key | `value` (e.g. "Enter", "Tab") |
| `scroll` | Scroll the page | `value` ("up"/"down"/pixels) |
| `handle_dialog` | Accept or dismiss a browser dialog | `value` ("accept"/"dismiss") |

### Flow Control

| Action | Description | Key Fields |
|---|---|---|
| `wait` | Wait for element, navigation, timeout, or JS expression | `type`, `selector` or `value` |
| `if` | Conditional branching | `condition`, `then`, `else` (optional) |
| `assert` | Verify element state with retry | `selector`, `state`, `on_fail` |

### Wait subtypes

| Type | Behavior | `value` |
|---|---|---|
| `element` (default) | Poll until selector appears | — |
| `navigation` | Wait for page load | — |
| `timeout` | Unconditional sleep | Duration in ms as string (e.g. `"3000"`) |
| `function` | Poll until JS expression returns truthy | JS expression string |

### Condition types

**State-based** (`exist`, `not_exist`, `visible`, `hidden`, `checked`):

```json
{ "selector": "#checkbox", "state": "checked" }
```

**Value-based** (`eq`, `ne`, `contains`, `matches_regex`):

```json
{ "selector": ".status", "attribute": "textContent", "operator": "eq", "expected_value": "Approved" }
```

---

## Selectors

Selectors are auto-detected by prefix. You can also set `selector_type` explicitly.

| Prefix | Type |
|---|---|
| `//` | XPath |
| `#` | ID |
| `[name=` | name attribute |
| `[placeholder=` | placeholder attribute |
| `[data-testid=` | data-testid attribute |
| (default) | CSS selector |

```json
{
  "action": "fill",
  "selector": "#email",
  "selector_fallbacks": ["[name='email']", "[data-testid='email-input']"],
  "value": "user@example.com"
}
```

The engine tries the primary selector first, then each fallback in order. Only if ALL fail does `optional` logic apply.

---

## PII Redaction

When `options.redact_pii` is `true` (default):

- **Logs**: all `value` fields are printed as `<redacted>`
- **Extracted text**: emails, phone numbers, Chinese 18-digit IDs, and US SSNs are masked with `***`
- **Per-field override**: set `redact: false` on individual `extract_schema.fields[]` to preserve raw values

---

## AI Agent Integration

web-auto-form ships with everything needed to work as an LLM tool:

- **JSON tool schema** ([web_auto_form_tool.json](web_auto_form_tool.json)) — drop it into any OpenAI/Claude function-calling pipeline
- **System prompt** ([SYSTEM_PROMPT.md](SYSTEM_PROMPT.md)) — trigger conditions, safety constraints, retry policies, and output format

### Demo: Claude/Cursor fills a form for you

See [docs/AI_AGENT_INTEGRATION.md](docs/AI_AGENT_INTEGRATION.md) for a step-by-step walkthrough with screenshots and a runnable demo script.

**In one sentence:** Tell Claude "fill out this job application with my resume," and Claude calls web-auto-form to do it in a real browser.

---

## Examples

| Example | Description |
|---|---|
| [job_application.json](examples/job_application.json) | Full workflow: templates, conditionals, assertions, fallbacks, file upload |
| [google_form.json](examples/google_form.json) | Minimal example: fill + click + navigation wait |
| [conditional_form.json](examples/conditional_form.json) | Nested if/else, value-based conditions, multi-assert with retry |

---

## Documentation

- [Steps Reference](docs/STEPS.md) — Every action type with all parameters
- [Selectors Guide](docs/SELECTORS.md) — Auto-detection, fallback chain, best practices
- [PII Redaction](docs/PII_REDACTION.md) — How redaction works, configuration
- [AI Agent Integration](docs/AI_AGENT_INTEGRATION.md) — Walkthrough for Claude/Cursor/agent setup
- [JSON Tool Schema](web_auto_form_tool.json) — Full input schema for LLM function-calling
- [System Prompt](SYSTEM_PROMPT.md) — Integration guide for AI agents
- [Contributing](docs/CONTRIBUTING.md) — Developer setup and PR workflow
- [Code of Conduct](docs/CODE_OF_CONDUCT.md) — Contributor Covenant 2.1

---

## Development

```bash
git clone https://github.com/DUZ1287/web-auto-form.git
cd web-auto-form

make dev          # install deps + Playwright Chromium
make test         # run unit tests
make lint         # flake8 + mypy
make format       # black + isort

# Run an example
make example

# Clean build artifacts
make clean
```

### Without Make

```bash
pip install -e ".[dev]"
playwright install chromium
python -m pytest -v
```

---

## Online Playground

Try web-auto-form instantly in your browser — no installation needed.

→ **[Launch Playground](https://huggingface.co/spaces/DUZ1287/web-auto-form)** (Hugging Face Spaces)

You can also run it locally:

```bash
pip install gradio
python playground/app.py
```

See [playground/README.md](playground/README.md) for details.

---

## CI

GitHub Actions on Python 3.9–3.12 (Ubuntu):

- **Lint**: flake8
- **Type check**: mypy
- **Format check**: black + isort
- **Tests**: pytest

Configuration: [`.github/workflows/ci.yml`](.github/workflows/ci.yml)

---

## License

[MIT](LICENSE)

---

## Project Structure

```text
web-auto-form/
├── src/web_auto_form/       # Core package
│   ├── __init__.py          # Public API: run(), run_from_path()
│   ├── cli.py               # Click CLI
│   ├── browser.py           # Playwright browser lifecycle
│   ├── models.py            # Pydantic validation models
│   ├── runner.py            # Step execution engine
│   ├── redact.py            # PII redaction (regex-based)
│   ├── selectors.py         # Selector detection & resolution
│   ├── templates.py         # {{variable}} rendering
│   └── actions/             # 13 action handlers
│       ├── navigate.py      # page.goto
│       ├── fill.py          # input fill
│       ├── click.py         # element click
│       ├── select.py        # dropdown select
│       ├── check.py         # checkbox toggle
│       ├── upload.py        # file upload (local/URL/data URI)
│       ├── wait.py          # element/navigation/timeout/function
│       ├── scroll.py        # page scroll
│       ├── extract.py       # text/attribute extraction
│       ├── press_key.py     # keyboard press
│       ├── handle_dialog.py # dialog accept/dismiss
│       ├── if_branch.py     # conditional evaluation
│       └── assertion.py     # state verification
├── tests/                   # Unit + integration tests
├── docs/                    # Reference documentation
├── examples/                # Example configs
├── playground/              # Gradio-based online playground
├── pyproject.toml           # Build & tool config
├── requirements.txt         # Runtime dependencies
├── Makefile                 # Dev shortcuts
├── web_auto_form_tool.json  # JSON tool schema (LLM integration)
├── SYSTEM_PROMPT.md         # AI agent integration guide
└── .github/workflows/ci.yml # CI pipeline
```
