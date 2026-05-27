# AI Agent Integration

How to make Claude, Cursor, or any LLM agent fill out web forms through web-auto-form.

---

## The Big Idea

> **You say "fill out this form" → The model generates a web-auto-form JSON config → web-auto-form executes it in a real browser → You get the result.**

No brittle scraping scripts. No Selenium boilerplate. The model is the planner; web-auto-form is the executor.

---

## Quick Demo

Here's the workflow in one terminal session:

```bash
# 1. Start the web-auto-form MCP server (or just use CLI)
python demo/mcp_server.py

# 2. In Claude/Cursor, say:
#    "Navigate to https://example.com/jobs/apply,
#     fill in name: Alice Chen, email: alice@example.com,
#     upload resume from ./alice_resume.pdf, and submit."

# 3. Claude generates a JSON config and calls web-auto-form.

# 4. Result comes back:
#    { "status": "success", "steps_executed": 5, "extracted": { ... } }
```

### What happens under the hood

```
User: "Fill this job application form for me"
         │
         ▼
    LLM (Claude / GPT)
         │ Reads: JSON tool schema + system prompt
         │ Understands: the form structure, what to fill
         │
         ▼
    Generated JSON config
         │ {
         │   "url": "https://jobs.example.com/apply",
         │   "consent_statement": "Filling job application for Alice Chen.",
         │   "data": { "name": "Alice Chen", "email": "alice@example.com", ... },
         │   "steps": [
         │     { "action": "fill", "selector": "#name", "value": "{{name}}" },
         │     { "action": "fill", "selector": "#email", "value": "{{email}}" },
         │     { "action": "upload", "selector": "#resume", "value": "./resume.pdf" },
         │     { "action": "click", "selector": "button[type='submit']" },
         │     { "action": "wait", "type": "navigation" },
         │     { "action": "extract", "selector": ".confirmation" }
         │   ],
         │   "extract_schema": {
         │     "fields": [
         │       { "name": "confirmation", "selector": ".alert-success" }
         │     ]
         │   }
         │ }
         │
         ▼
    web-auto-form engine (Playwright)
         │ Opens Chromium → fills form → submits → extracts results
         │
         ▼
    Result returned to LLM → response back to user
         "Form submitted successfully. Confirmation message: 
          'Your application has been received. Ref #APP-2026-0042.'"
```

---

## Integration Methods

### Method 1: MCP Server (Recommended for Claude Desktop / Cursor)

web-auto-form works as an MCP (Model Context Protocol) tool. The agent can discover and invoke it automatically.

**Setup:**

```bash
# Install
pip install web-auto-form mcp

# Create an MCP server entrypoint
# See demo/mcp_server.py for a ready-to-use implementation
```

**Claude Desktop config** (`claude_desktop_config.json`):

```json
{
  "mcpServers": {
    "web-auto-form": {
      "command": "python",
      "args": ["demo/mcp_server.py"]
    }
  }
}
```

After setup, Claude can directly call `web_auto_form` as a tool:

```
User: "Register an account at https://example.com/signup for me"
Claude: [calls web_auto_form tool with JSON config]
Claude: "Done! Account registered successfully. Confirmation email sent to alice@example.com."
```

### Method 2: Direct Tool Schema (OpenAI / Anthropic API)

Drop the tool schema into any function-calling pipeline:

```python
import json
import anthropic
from web_auto_form import run

# Load the tool schema
with open("web_auto_form_tool.json") as f:
    tool_schema = json.load(f)

# Load the system prompt
with open("SYSTEM_PROMPT.md") as f:
    system_prompt = f.read()

client = anthropic.Anthropic()

response = client.messages.create(
    model="claude-sonnet-4-6",
    system=system_prompt,
    tools=[tool_schema],
    messages=[
        {"role": "user", "content": "Fill out the registration form at https://example.com/register with name=John, email=john@example.com"}
    ],
)

# If Claude decides to call the tool
if response.stop_reason == "tool_use":
    for block in response.content:
        if block.type == "tool_use" and block.name == "web_auto_form":
            config = block.input
            result = run(config)
            print(f"Status: {result['status']}")
            print(f"Extracted: {result['extracted']}")
```

### Method 3: CLI as Subprocess (Any LLM / Agent Framework)

```python
import json
import subprocess
import tempfile

def llm_call_web_auto_form(config: dict) -> dict:
    """Called by the LLM agent framework when it decides to use this tool."""
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".json", delete=False
    ) as f:
        json.dump(config, f)
    
    result = subprocess.run(
        ["web_auto_form", "run", f.name, "--output", "-"],
        capture_output=True, text=True
    )
    return json.loads(result.stdout)
```

---

## The System Prompt

The key to reliable LLM behavior is a good system prompt. web-auto-form ships with a comprehensive one at [SYSTEM_PROMPT.md](../SYSTEM_PROMPT.md).

Key safety rules baked into the prompt:

| Rule | Why |
|---|---|
| `consent_statement` required | Prevents unauthorized automation |
| Max 50 steps per invocation | Prevents runaway loops |
| `step_delay_ms >= 100` enforced | Avoids triggering anti-bot detection |
| PII redaction on by default | Privacy by default |
| `sandbox: true` by default | Prevents malicious page escape |
| No credential harvesting | Ethical boundary hard-coded |
| No CAPTCHA / 2FA bypass | Respects security controls |

---

## Real-World Use Cases

### 1. Job Application Automation

> "Apply to this job posting with my resume and cover letter."

The LLM reads the job posting URL, understands the form structure, generates a config with fill/upload/click steps, and web-auto-form executes it. The extracted confirmation number is returned.

### 2. Batch Data Entry

> "Register these 100 users from users.csv."

The LLM generates one config with `data`, then a script iterates over the CSV, calling `run()` with different data for each row.

### 3. Form Testing in CI

> "After deploy, verify the signup form still works end-to-end."

A CI pipeline runs web-auto-form against staging. Assertions verify every field, and the exit code gates the deployment.

### 4. Scheduled Form Submission

> "Submit the daily attendance form at 9 AM every weekday."

A cron job runs `web_auto_form run attendance.json --data date=$(date +%Y-%m-%d)`.

---

## Tips for Reliable LLM → Config Generation

1. **Put the system prompt first** — The safety rules should be the first thing the model reads
2. **Include examples in the prompt** — A few `user → config` examples dramatically improve output quality
3. **Validate before executing** — web-auto-form's Pydantic models validate the config; malformed configs are rejected with clear errors
4. **Let the engine handle retries** — Don't ask the LLM to implement retry logic; use `max_retries` and `selector_fallbacks`
5. **Use `description` fields** — They help the LLM understand what each step does

---

## Run the Demo

```bash
# Install
pip install -e ".[dev]"

# Run the interactive demo
python demo/demo_agent.py

# It will:
# 1. Accept a task in natural language
# 2. Show the generated web-auto-form JSON config
# 3. Execute it in a browser
# 4. Display the results
```

Example session:

```
$ python demo/demo_agent.py

Enter your task: Fill the contact form at https://httpbin.org/forms/post 
with name=Jane Doe, email=jane@example.com, and choose "Support" from 
the department dropdown, then submit.

Generating config...
────────────────────────────────────────
{
  "url": "https://httpbin.org/forms/post",
  "consent_statement": "Filling contact form for user Jane Doe.",
  "data": {
    "name": "Jane Doe",
    "email": "jane@example.com"
  },
  "steps": [
    {"action": "fill", "selector": "#name", "value": "{{name}}"},
    {"action": "fill", "selector": "#email", "value": "{{email}}"},
    {"action": "select", "selector": "#department", "value": "Support"},
    {"action": "click", "selector": "button[type='submit']"}
  ]
}
────────────────────────────────────────
Execute? (y/n): y

Running web-auto-form...
✓ Step 0: fill   #name              → <redacted>   (340ms)
✓ Step 1: fill   #email             → <redacted>   (280ms)
✓ Step 2: select #department         → Support     (410ms)
✓ Step 3: click  button[type=submit]               (520ms)

Status: success
Steps executed: 4
Steps failed: 0
```
