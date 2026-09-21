# Selectors and Locators

## Two forms

| Form | Example | Status |
| --- | --- | --- |
| `selector` (string) | `{"selector": "#email"}` | supported, unchanged |
| `locator` (structured) | `{"locator": {"strategy": "label", "value": "Email"}}` | preferred for new config |

Both target an element. A step may use either, but **not both** — supplying
`selector` and `locator` together is a validation error, and mixing
`selector_fallbacks` with `locator_fallbacks` likewise. The engine will not guess
which one wins.

## Strategies

| Strategy | Fields | Resolves to |
| --- | --- | --- |
| `role` | `role`, `name`, `exact` | `page.get_by_role()` |
| `label` | `value`, `exact` | `page.get_by_label()` |
| `text` | `value`, `exact` | `page.get_by_text()` |
| `placeholder` | `value`, `exact` | `page.get_by_placeholder()` |
| `testid` | `value` | `page.get_by_test_id()` |
| `id` | `value` | `[id="…"]` |
| `name` | `value` | `[name="…"]` |
| `attr` | `attr`, `op`, `value`, `prefix` | `[attr op "…"]` |
| `css` | `value` | raw CSS, verbatim |
| `xpath` | `value` | raw XPath, verbatim |

```json
{"action": "fill", "locator": {"strategy": "label", "value": "Email"}, "value": "a@b.com"}

{"action": "click", "locator": {"strategy": "role", "role": "button", "name": "Submit"}}

{"action": "fill", "locator": {"strategy": "attr", "attr": "href", "op": "^=",
                               "value": "https://", "prefix": "a.nav"}}
```

### `exact`

Playwright's text matchers are substring + whitespace-normalized by default, so
`get_by_label("Save")` also matches "Save and continue". Pass `exact: true` when
that would be ambiguous. `id`, `name`, `attr` and `testid` are always exact
attribute matches and ignore the flag.

## Auto-detection (legacy `selector`)

When `selector_type` is omitted, the type is detected from the prefix:

| Prefix | Detected Type | Example |
| --- | --- | --- |
| `//` | XPath | `//div[@id='form']` |
| `#` (no spaces) | ID | `#fullname` |
| `[name=` | Name attribute | `[name='email']` |
| `[placeholder=` | Placeholder | `[placeholder='Phone']` |
| `[data-testid=` | Data test ID | `[data-testid='submit']` |
| Everything else | CSS | `div.form > input` |

A selector that already contains a placeholder is normalized into an explicit
strategy *before* rendering, so substitution never influences which detection
branch runs.

## Template safety

The trust boundary is the placeholder:

* **No `{{…}}`** — authored configuration. Used verbatim, exactly as before.
* **Has `{{…}}`** — carrying untrusted data. It is confined to a value slot that
  can be escaped correctly for its grammar.

| Strategy | Placeholders | Handling |
| --- | --- | --- |
| `role`, `label`, `text`, `placeholder`, `testid` | allowed | passed to Playwright as an **argument**, never assembled into selector grammar |
| `id`, `name`, `attr` | allowed | emitted as a quoted CSS attribute value, escaped for that context |
| `css` | only in an attribute-value slot, with a literal prefix / attribute name / operator | `[name='{{x}}']`, `input[name='{{x}}']`, `[href^='{{u}}']` |
| `xpath` | **none** | XPath 1.0 string literals have no escape character |

Everything else is refused with `TEMPLATE_ERROR` before the browser starts:

```text
div.{{cls}} > input          # placeholder in a grammar position
//div[@id='{{x}}']           # XPath
[{{attr}}='literal']         # placeholder in the attribute *name*
[name='{{x}}'] [type='text'] # a second grammar position after the value slot
```

The prefix in `input[name='{{x}}']` is preserved verbatim, so the combinator
spacing the author wrote survives: `#wrap [name='{{x}}']` stays a descendant
selector, not a compound one.

For the cases that cannot be escaped, use a semantic strategy instead — it is
both safer and more robust:

```json
{"selector": "[name='{{field}}']"}                          // works...
{"locator": {"strategy": "name", "value": "{{field}}"}}      // ...but prefer this
```

### Escaping, precisely

Attribute values are emitted as **double-quoted CSS strings**. Inside one, only
`\`, `"` and raw newline / CR / form-feed can terminate or corrupt the string;
those are escaped (control characters as CSS hex escapes — `\a` for newline,
`\d` for CR, `\c` for form-feed — each followed by a space, which is required so
that a hex digit from the data cannot merge into the escape). NUL is refused
rather than escaped, because CSS maps U+0000 to U+FFFD and the result would match
a *different* element.

## Fallback chain

```json
{
  "action": "click",
  "locator": {"strategy": "css", "value": "#submit-btn"},
  "locator_fallbacks": [
    {"strategy": "testid", "value": "submit-btn"},
    {"strategy": "role", "role": "button", "name": "Submit"}
  ]
}
```

Resolution:

1. Try the primary.
2. If it matches nothing, try each fallback in order; the first match wins.
3. A **structural** failure — invalid selector syntax, closed target — aborts the
   chain with `INVALID_SELECTOR`. A malformed candidate means the configuration is
   wrong; silently using a backup would hide the defect and make behaviour depend
   on which candidate happened to be broken.
4. Only if every candidate matches nothing does the `optional` logic apply
   (`optional: true` → recorded as `skipped`; otherwise `ELEMENT_NOT_FOUND`).

## Best practices

- **Prefer `role` / `label` / `testid`** — they are tied to accessible meaning
  and survive the DOM renames that break id and class selectors.
- **Then `placeholder` / `text` / `name`**, then stable CSS, with **XPath last**.
- **Always provide fallbacks** for critical steps (submit, upload).
- **Avoid generated ids** like `id="input_123456"` and positional selectors like
  `div > div:nth-child(3) > input`.
