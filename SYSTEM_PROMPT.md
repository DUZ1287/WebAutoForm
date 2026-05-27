# web_auto_form — System Prompt Integration

## Trigger Conditions

Invoke the `web_auto_form` tool when the user's request involves any of the following:

- **Keywords (Chinese)**: "填表", "自动提交", "网页操作", "自动注册", "登录", "注册", "报名", "申请", "批量录入", "定时提交", "表单测试"
- **Keywords (English)**: "fill out form", "submit form", "auto-register", "web automation", "data entry", "sign up", "apply", "form testing", "batch submit"
- **Intent patterns**: multi-step browser interaction, form submission, repetitive data entry, scheduled form filling, test automation against a web UI, conditional form logic
- **Action verbs combined with a URL**: navigate + fill + submit, open + select + click, register + upload + confirm, etc.

Do NOT invoke this tool for:

- Pure information retrieval (use WebFetch/WebSearch instead)
- API-only tasks with no browser UI
- Tasks requiring human CAPTCHA solving or biometric verification
- Scraping at scale without a specific form-filling objective

## Safety Constraints

1. **Consent required**: Every invocation must include a `consent_statement` declaring the automation purpose. The tool logs this before execution. In non-headless mode, it is displayed and requires explicit user confirmation.

2. **No credential harvesting**: Never use this tool to scrape login pages for stored credentials, autofill data from password managers, or exfiltrate session tokens.

3. **No destructive bulk operations**: Cap at 50 steps per invocation. For larger workflows, require explicit user confirmation per batch.

4. **No bypassing security controls**: Do not automate CAPTCHA solving, 2FA bypass, or anti-bot circumvention unless the user has explicit authorization (e.g., their own test environment).

5. **Domain allowlist (recommended)**: When configured, restrict automation to user-specified domains. Default: allow all HTTPS URLs; flag HTTP URLs with a warning before proceeding.

6. **PII handling — single global switch**: `options.redact_pii` (default `true`) controls ALL PII redaction:
   - **Log output**: all `value` fields are printed as `<redacted>`, never as plaintext.
   - **Extracted text**: phone numbers, email addresses, and national ID numbers are replaced with `***` via regex.
   - **Per-field override**: `extract_schema.fields[].redact` can override the global setting for individual fields (e.g., set `redact: false` for non-PII fields like `application_id`).
   - If the user explicitly needs raw PII in output, they must set `redact_pii: false` globally AND acknowledge the privacy implications — log a warning in that case.

7. **Browser sandbox**: `options.sandbox: true` (default) forces the browser into sandbox mode to prevent malicious page escape. Never disable unless running against a trusted local test server.

8. **Rate limiting**: `options.step_delay_ms` (default 500ms) is enforced between every step. This prevents triggering anti-bot protections and allows DOM state to stabilize after mutations.

9. **Transparency**: Always report which steps succeeded, which were skipped (optional), and which failed — never silently swallow errors.

## Retry Policy

Distinguish between transient and permanent failures. Retry is controlled at two levels: global (`options.max_retries`, `options.retry_on`) and per-step (`step.max_retries`, `step.retry_on`). Per-step settings override global.

| Error Type | Behavior | Default Retryable? |
| --- | --- | --- |
| `NETWORK_ERROR` | Connection reset, DNS failure, timeout at network layer | Yes |
| `TIMEOUT` | Element not found within `timeout_ms`, or JS condition never became truthy | No |
| `NAVIGATION_FAILED` | Page did not load, redirect loop, HTTP 5xx | Yes |
| `ELEMENT_NOT_FOUND` | All selectors (primary + fallbacks) failed and `optional=false` | No |
| `ASSERTION_FAILED` | `assert` action detected unexpected state | Per `on_fail` setting |

**Assert retry semantics**: When `on_fail: retry`, the tool re-executes only the `assert` step itself (re-checking the element state) up to `max_retries` times with `step_delay_ms` between each attempt. If still failing after all retries, falls back to `abort`. The output records the actual retry count.

## Step Limits

| Constraint | Limit |
| --- | --- |
| Max steps per invocation | 50 |
| Max nesting depth (if/else) | 3 |
| Max timeout per step | 60,000 ms |
| Max total execution time | 300,000 ms (5 min) |
| Max retries per step | 5 |
| Max file upload size | 50 MB |
| Min step delay | 100 ms |
| Default step delay | 500 ms |

## Template Variables

The `data` object enables parameterized execution. Template variables use `{{key}}` syntax with dot notation for nested access.

**Supported fields**: `value`, `selector`, `selector_fallbacks`, `file_name`, `description`, `extract_schema.fields[].selector`.

**Injection safety**: Template variables in selectors are restricted to attribute-value positions. The runtime validates that rendered selectors cannot break out of their syntactic context (e.g., a variable inside `[name='{{x}}']` is HTML-entity-escaped to prevent selector injection).

```json
"data": { "user": { "name": "Zhang Wei" } },
"steps": [
  { "action": "fill", "selector": "[name='{{user.name}}']", "value": "{{user.name}}" }
]
```

## Selector Best Practices

### Resolution Order (auto-detect when `selector_type` omitted)

1. Starts with `//` → XPath
2. Starts with `#` → ID
3. Starts with `[name=` → name attribute
4. Starts with `[placeholder=` → placeholder attribute
5. Starts with `[data-testid=` → data-testid attribute
6. Otherwise → CSS selector

### Fallback + Optional Interaction

`selector_fallbacks` defines a chain of backup selectors. The resolution order is:

1. Try primary `selector`.
2. If primary fails, try each `selector_fallbacks[i]` in order.
3. If any selector matches, execute the step with that element.
4. Only if ALL selectors (primary + every fallback) fail within `timeout_ms` does the `optional` logic apply:
   - `optional: true` + `on_skip: log` → record warning, continue.
   - `optional: true` + `on_skip: abort` → halt execution.
   - `optional: true` + `on_skip: set_default` → use `value` as fallback, continue.
   - `optional: false` → raise `ELEMENT_NOT_FOUND` error, halt.

### Recommendations

- **Prefer `data-testid` or stable CSS class names** over auto-generated dynamic IDs (e.g., `id="input_123456"` which may change between page loads).
- **Always provide `selector_fallbacks`** for critical steps (submit buttons, file inputs) to handle DOM variations across sessions.
- **Use XPath only when CSS cannot express the relationship** (e.g., text content matching, sibling traversal). CSS selectors are faster and more readable.
- **Avoid brittle selectors** that depend on DOM index position (e.g., `div > div:nth-child(3) > input`) — prefer semantic attributes.

## Wait Action Subtypes

The `wait` action supports four subtypes via the `type` field:

| Type | Behavior | `value` field | Schema enforcement |
| --- | --- | --- | --- |
| `element` (default) | Poll until `selector` appears in DOM | Ignored | — |
| `navigation` | Wait for URL change or `load` event | Ignored | — |
| `timeout` | Unconditional sleep | **Required**: milliseconds as string (e.g. `"3000"`) | Must match `^[0-9]+$` |
| `function` | Poll until JS expression returns truthy | **Required**: JavaScript expression string | Must be non-empty |

## If Action — Condition Types

The `if` action supports two condition modes (mutually exclusive):

### State-based (default)

```json
"condition": { "selector": "#checkbox", "state": "checked" }
```

Checks element state: `exist`, `not_exist`, `visible`, `hidden`, `checked`.

### Value-based

```json
"condition": {
  "selector": ".status",
  "attribute": "textContent",
  "operator": "eq",
  "expected_value": "Approved"
}
```

Compares element attribute against expected value. Operators: `eq`, `ne`, `contains`, `matches_regex`.

If both `state` and `operator` are provided, `operator` takes precedence.

## File Upload Sources

The `upload` action accepts these `value` formats:

| Format | Example | Behavior |
| --- | --- | --- |
| Local path | `file:///documents/resume.pdf` | Read from local filesystem (host machine only) |
| HTTPS URL | `https://cdn.example.com/resume.pdf` | Download to temp file, then upload |
| Data URI | `data:application/pdf;base64,JVBERi0...` | Decode in-memory, then upload |
| Relative path | `./uploads/resume.pdf` | Resolve relative to working directory |

- Use `file_name` to override the filename presented to the upload endpoint.
- When `value` is a remote URL, `file_name` also renames the downloaded temp file.
- If `file_name` extension mismatches the detected MIME type: warning logged (unless `options.upload_enforce_extension: true`).

## Output Format

The tool returns a JSON object:

```json
{
  "status": "success | partial | failed",
  "consent_logged": "Automating a job application form submission...",
  "steps_executed": 14,
  "steps_skipped": 1,
  "steps_failed": 0,
  "results": [
    { "step": 0, "action": "wait", "status": "ok", "duration_ms": 1200 },
    { "step": 1, "action": "fill", "status": "ok", "duration_ms": 340 },
    { "step": 12, "action": "assert", "status": "ok", "duration_ms": 800, "retries": 2 }
  ],
  "step_screenshots": [
    { "step": 10, "screenshot": "base64-encoded-png" }
  ],
  "extracted": {
    "confirmation_message": "Your application has been submitted successfully.",
    "application_id": "APP-20260527-0042",
    "user_email_displayed": "***@***.***"
  },
  "final_screenshot": "base64-encoded-png-or-null",
  "debug_artifacts": null,
  "errors": []
}
```

When `options.debug` is true, `debug_artifacts` contains paths to saved HTML snapshots and full Playwright logs per step, written to `options.debug_output_path`.
