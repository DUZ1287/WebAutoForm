# Steps Reference

Each step in the `steps` array is an atomic browser operation executed sequentially.

## Common Fields

All steps share these optional fields:

| Field | Type | Default | Description |
| --- | --- | --- | --- |
| `action` | string | *required* | The action to perform |
| `description` | string | `null` | Human-readable label (supports `{{template}}` vars) |
| `optional` | bool | `false` | Record as `skipped` instead of failing the workflow |
| `on_skip` | string | `"log"` | Only for `optional` steps: `"log"`, `"abort"`, or `"set_default"` |
| `on_fail` | string | `"abort"` | Failure policy for every action: `"abort"`, `"continue"`, or `"retry"` |
| `max_retries` | int | global | Additional attempts on top of the first (1–5) |
| `retry_on` | string[] | global | Error codes eligible for retry, e.g. `["NETWORK_ERROR", "TIMEOUT"]` |
| `screenshot` | bool | `false` | Capture screenshot after this step |
| `timeout_ms` | int | `5000` | Max wait for element (0–60000) |
| `selector` | string | `null` | Legacy string locator (required for most actions unless `locator` is given) |
| `locator` | object | `null` | Structured locator — see [SELECTORS.md](SELECTORS.md). Mutually exclusive with `selector` |
| `selector_type` | string | auto | `"css"`, `"xpath"`, `"id"`, `"name"`, `"placeholder"`, `"data-testid"` |
| `selector_fallbacks` | string[] | `[]` | Backup selectors tried in order |
| `locator_fallbacks` | object[] | `[]` | Backup locators; requires `locator` |

```json
{"action": "fill", "locator": {"strategy": "label", "value": "Email"}, "value": "a@b.com"}
{"action": "click", "locator": {"strategy": "role", "role": "button", "name": "Submit"}}
```

A step may use `selector` or `locator`, never both. Template variables are
allowed only in positions that can be escaped — see
[SELECTORS.md](SELECTORS.md#template-safety).

---

## Actions

### `navigate`

Open a URL.

| Field | Required | Description |
| --- | --- | --- |
| `value` | Yes | The URL to navigate to |

```json
{"action": "navigate", "value": "https://example.com"}
```

### `fill`

Type text into an input field.

| Field | Required | Description |
| --- | --- | --- |
| `selector` | Yes | Target input element |
| `value` | Yes | Text to type (supports `{{template}}`) |

```json
{"action": "fill", "selector": "#email", "value": "{{user.email}}"}
```

### `select`

Choose an option from a dropdown.

| Field | Required | Description |
| --- | --- | --- |
| `selector` | Yes | Target `<select>` element |
| `value` | Yes | Option label or value |

```json
{"action": "select", "selector": "#country", "value": "US"}
```

### `check`

Check or uncheck a checkbox/radio.

| Field | Required | Description |
| --- | --- | --- |
| `selector` | Yes | Target checkbox/radio |
| `value` | No | `"true"` (default) to check, `"false"` to uncheck |

```json
{"action": "check", "selector": "#agree", "value": "true"}
```

### `click`

Click any element.

| Field | Required | Description |
| --- | --- | --- |
| `selector` | Yes | Target element |

```json
{"action": "click", "selector": "button[type='submit']"}
```

### `upload`

Upload a file via a file input.

| Field | Required | Description |
| --- | --- | --- |
| `selector` | Yes | Target `<input type="file">` |
| `value` | Yes | Local path, `https://` URL, `data:` URI, or `file:` URL |
| `file_name` | No | Override upload filename |

```json
{"action": "upload", "selector": "#resume", "value": "file:///docs/resume.pdf"}
```

### `wait`

Wait for an element, navigation, timeout, or JS condition.

| Field | Required | Description |
| --- | --- | --- |
| `type` | No | `"element"` (default), `"navigation"`, `"timeout"`, `"function"` |
| `selector` | For `element` | Element to wait for |
| `value` | For `timeout`/`function` | Milliseconds (timeout) or JS expression (function) |

```json
{"action": "wait", "type": "navigation", "timeout_ms": 10000}
{"action": "wait", "type": "timeout", "value": "2000"}
{"action": "wait", "type": "function", "value": "() => document.title === 'Done'"}
```

### `scroll`

Scroll the page.

| Field | Required | Description |
| --- | --- | --- |
| `value` | No | `"up"`, `"down"` (default), or pixel count as string |

```json
{"action": "scroll", "value": "down"}
```

### `extract`

Extract text or attributes from an element.

| Field | Required | Description |
| --- | --- | --- |
| `selector` | Yes | Target element |
| `value` | No | `"text"` (default), `"innerHTML"`, `"value"`, or attribute name |

```json
{"action": "extract", "selector": ".price", "value": "textContent"}
```

### `press_key`

Press a keyboard key.

| Field | Required | Description |
| --- | --- | --- |
| `value` | No | Key name: `"Enter"`, `"Tab"`, `"Escape"`, etc. |

```json
{"action": "press_key", "value": "Enter"}
```

### `handle_dialog`

Accept or dismiss browser dialogs (alerts, confirms, prompts).

| Field | Required | Description |
| --- | --- | --- |
| `value` | No | `"accept"` (default) or `"dismiss"` |

```json
{"action": "handle_dialog", "value": "accept"}
```

### `assert`

Verify element state. Performs **one** check and reports `ASSERTION_FAILED` on a
miss — it has no retry loop of its own. Retrying is the engine's job, driven by
`on_fail` / `max_retries` exactly as for every other action.

| Field | Required | Description |
| --- | --- | --- |
| `selector` | Yes | Target element |
| `state` | Yes | `"exist"`, `"not_exist"`, `"visible"`, `"hidden"`, `"enabled"`, `"disabled"`, `"checked"` |
| `on_fail` | No | `"abort"` (default), `"continue"`, `"retry"` — retry re-runs the assert up to `max_retries`, then aborts |
| `max_retries` | No | Additional attempts on top of the first (1–5) |

```json
{"action": "assert", "selector": ".error", "state": "not_exist", "on_fail": "abort"}
```

### `if`

Conditional branching based on element state or value.

| Field | Required | Description |
| --- | --- | --- |
| `condition` | Yes | See [Condition Object](#condition-object) |
| `then` | Yes | Steps to execute when condition is true |
| `else` | No | Steps to execute when condition is false |

#### Condition Object

**State-based:**
```json
{"selector": "#checkbox", "state": "checked"}
```

**Value-based:**
```json
{"selector": ".status", "attribute": "textContent", "operator": "eq", "expected_value": "Approved"}
```

Operators: `eq`, `ne`, `contains`, `matches_regex`

```json
{
  "action": "if",
  "condition": {"selector": "#has_experience", "state": "checked"},
  "then": [
    {"action": "fill", "selector": "#years", "value": "5"}
  ],
  "else": [
    {"action": "check", "selector": "#fresh_grad", "value": "true"}
  ]
}
```
