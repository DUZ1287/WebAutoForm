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

## Failure Semantics

Every step failure is classified into a machine-readable error code, then mapped
onto a control-flow decision by the engine. **Action handlers never retry on
their own — the Runner is the single owner of retry.**

### Error codes

| Code | Meaning |
| --- | --- |
| `ELEMENT_NOT_FOUND` | No selector in the fallback chain matched within `timeout_ms` |
| `ELEMENT_NOT_VISIBLE` | Element exists but never became visible/stable in time |
| `ELEMENT_NOT_INTERACTABLE` | Element is covered, disabled, or outside the viewport |
| `TIMEOUT` | Timeout not attributable to a locator or a navigation |
| `NAVIGATION_FAILED` | Page did not load, redirect loop, frame detached |
| `NETWORK_ERROR` | Connection reset, DNS failure, connection refused |
| `INVALID_SELECTOR` | Selector is syntactically invalid |
| `ASSERTION_FAILED` | `assert` action detected an unexpected state |
| `FILE_UPLOAD_FAILED` | Upload source missing/unreadable, or the file input rejected it |
| `TEMPLATE_ERROR` | `{{variable}}` rendering produced an invalid step |
| `INTERNAL_ERROR` | Unexpected error raised by the engine itself |
| `UNKNOWN` | Unclassified failure |

### Failure policy

Resolution order for a failed step:

1. `optional: true` → recorded as `skipped`, workflow continues. `on_skip`
   refines this: `log` (default) and `set_default` continue, `abort` stops the
   workflow.
2. `on_fail: continue` → recorded as `failed`, workflow continues.
3. `on_fail: abort` (default), or `on_fail: retry` after its budget is spent →
   recorded as `failed` and the workflow stops immediately.

An abort raised inside a nested `if` branch propagates outward: the rest of that
branch and every later top-level step are skipped.

### Retry

`max_retries` counts **additional** attempts on top of the first. With
`max_retries: 2` a step runs at most 3 times and reports `retries: 2`.

An attempt is retried when either:

- the error code is listed in `retry_on` **and** that code is intrinsically
  retryable, or
- the step sets `on_fail: retry` — an explicit per-step instruction that
  overrides the retryability gate.

Intrinsically retryable: `TIMEOUT`, `NETWORK_ERROR`, `NAVIGATION_FAILED`,
`ELEMENT_NOT_VISIBLE`, `ELEMENT_NOT_INTERACTABLE`.
Never retryable: `ELEMENT_NOT_FOUND`, `INVALID_SELECTOR`, `ASSERTION_FAILED`,
`FILE_UPLOAD_FAILED`, `TEMPLATE_ERROR`, `INTERNAL_ERROR`, `UNKNOWN`.

`retry_on` (global or per-step) is the *policy* gate; `retryable` is a property
of the error itself. With the default `retry_on: ["NETWORK_ERROR"]` a timeout is
never retried, even though it is intrinsically retryable. `step_delay_ms` is
applied between attempts. Diagnostics (screenshot + page form elements) are
captured once, on the final failed attempt — not on every retry.

### Assert

`assert` performs **exactly one** check and reports `ASSERTION_FAILED` on a miss;
it has no retry loop of its own. `on_fail` applies to it exactly as it does to
every other action: `abort` (default) stops the workflow, `continue` keeps it
running, `retry` re-runs the assert up to `max_retries` times and aborts if it
still fails. The output records the actual attempt count in `retries`.

## Step Limits

| Constraint | Limit |
| --- | --- |
| Max steps per invocation | 50 |
| Max nesting depth (if/else) | 3 |
| Max timeout per step | 60,000 ms |
| Max total execution time | `options.max_total_ms`, default 300,000 ms (5 min) |
| Max retries per step | 5 |
| Max file upload size | 50 MB |
| Min step delay | 100 ms |
| Default step delay | 500 ms |

`max_total_ms` is the single workflow budget. Steps are not started once it is
spent, and a `wait` longer than the remaining budget fails with `TIMEOUT` instead
of sleeping past it.

## Template Variables

The `data` object enables parameterized execution. Template variables use `{{key}}` syntax with dot notation for nested access.

**Supported fields**: `value`, `file_name`, `description`, `selector`,
`selector_fallbacks`, `extract_schema.fields[].selector`, `condition.expected_value`,
and every field of a structured `locator`.

**Injection safety.** Template data must not be able to change a locator's
structure or make it target a different element. What that requires depends on
the strategy, so the strategy comes from the configuration and is never inferred
from the substituted text:

| Strategy | Placeholders | How the value is handled |
| --- | --- | --- |
| `role`, `label`, `text`, `placeholder`, `testid` | allowed | passed to `page.get_by_*()` as an **argument** — never assembled into selector grammar |
| `id`, `name`, `attr` | allowed | confined to a quoted CSS attribute value and escaped for that context |
| `css` | only in an attribute-value slot, with a literal prefix/name/operator | e.g. `[name='{{x}}']`, `input[name='{{x}}']` |
| `xpath` | **none** | XPath 1.0 has no string escape character, so it cannot be done safely |

Anywhere else — `div.{{cls}}`, `//div[@id='{{x}}']`, `[{{attr}}='v']` — the run
fails with `TEMPLATE_ERROR` before the browser is touched. A selector with no
placeholder is authored config and is used verbatim.

Two non-selector fields are restricted for the same reason: `wait` with
`type: function` (its `value` is JavaScript evaluated in page context) and
`if` with `operator: matches_regex` (its `expected_value` becomes the regex
pattern, where crafted input causes catastrophic backtracking).

```json
"data": { "user": { "name": "Zhang Wei" } },
"steps": [
  { "action": "fill", "selector": "[name='{{user.name}}']", "value": "{{user.name}}" }
]
```

## Locators

### Prefer the structured `locator`

Two forms target an element. `selector` is the legacy string form and keeps
working unchanged; `locator` states the strategy explicitly and is what new
config should use. Giving both on one step is a validation error — the engine
will not guess which wins.

```json
{ "action": "fill", "locator": { "strategy": "label", "value": "Email" }, "value": "a@b.com" }
{ "action": "click", "locator": { "strategy": "role", "role": "button", "name": "Submit" } }
```

| Strategy | Fields | Resolves to |
| --- | --- | --- |
| `role` | `role`, `name`, `exact` | `page.get_by_role()` |
| `label` / `text` / `placeholder` | `value`, `exact` | `page.get_by_label()` / `get_by_text()` / `get_by_placeholder()` |
| `testid` | `value` | `page.get_by_test_id()` |
| `id` / `name` | `value` | `[id="…"]` / `[name="…"]` |
| `attr` | `attr`, `op`, `value`, `prefix` | `[attr op "…"]`, optionally prefixed |
| `css` / `xpath` | `value` | raw, used verbatim — no placeholders allowed |

`locator_fallbacks` is the structured equivalent of `selector_fallbacks`.

### Recommended order of preference

1. `role` / `label` / `testid` — tied to accessible meaning, survives refactors
2. `placeholder` / `text` / `name`
3. stable CSS (a real class or attribute, not generated ids)
4. XPath — last resort

Pass `exact: true` when a substring match would be ambiguous:
`get_by_label("Save")` also matches "Save and continue".

### Resolution Order (auto-detect when `selector_type` omitted)

1. Starts with `//` → XPath
2. Starts with `#` → ID
3. Starts with `[name=` → name attribute
4. Starts with `[placeholder=` → placeholder attribute
5. Starts with `[data-testid=` → data-testid attribute
6. Otherwise → CSS selector

This sniffing applies to configuration without placeholders. A selector that
*does* contain one is normalized into an explicit strategy first, so the data
never influences which rule applies.

### Fallback + Optional Interaction

`selector_fallbacks` / `locator_fallbacks` define a chain of backup locators.
The resolution order is:

1. Try the primary.
2. If it does not match, try each fallback in order.
3. If any candidate matches, execute the step with that element.
4. A candidate that *fails structurally* — invalid selector syntax, closed
   target — aborts the chain with `INVALID_SELECTOR` rather than falling through.
   A malformed locator means the configuration is wrong, and quietly using a
   backup would hide that. Only a candidate that simply matches nothing advances.
5. Only if ALL candidates fail within `timeout_ms` does the `optional` logic apply:
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
  "aborted": false,
  "steps_executed": 14,
  "steps_skipped": 1,
  "steps_failed": 0,
  "results": [
    { "step": 0, "action": "wait", "status": "ok", "duration_ms": 1200 },
    { "step": 1, "action": "fill", "status": "ok", "duration_ms": 340 },
    { "step": 12, "action": "assert", "status": "ok", "duration_ms": 800, "retries": 2 },
    {
      "step": 13,
      "action": "click",
      "status": "failed",
      "duration_ms": 5000,
      "error": "Timeout 5000ms exceeded.",
      "error_code": "ELEMENT_NOT_VISIBLE",
      "retryable": true,
      "diagnostics": { "screenshot": "base64-encoded-png", "form_elements": [] }
    }
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

`status` is derived from the failure policy, not from counting steps:

| `status` | Meaning |
| --- | --- |
| `success` | Every step succeeded, or failed only as an `optional` step (recorded `skipped`) |
| `partial` | The workflow ran to completion but at least one non-optional step failed with `on_fail: continue` |
| `failed` | The workflow aborted — `on_fail: abort`, an exhausted `on_fail: retry`, or an unrecoverable engine error |

`aborted: true` means the workflow stopped early. Failed steps additionally carry
`error_code` and `retryable`; every failure is also summarised in `errors`.

When `options.debug` is true, `debug_artifacts` contains paths to saved HTML snapshots and full Playwright logs per step, written to `options.debug_output_path`.
