# Selectors Guide

## Auto-Detection

When `selector_type` is omitted, the type is detected automatically:

| Prefix | Detected Type | Example |
| --- | --- | --- |
| `//` | XPath | `//div[@id='form']` |
| `#` (no spaces) | ID | `#fullname` |
| `[name=` | Name attribute | `[name='email']` |
| `[placeholder=` | Placeholder | `[placeholder='Phone']` |
| `[data-testid=` | Data test ID | `[data-testid='submit']` |
| Everything else | CSS | `div.form > input` |

## Fallback Chain

`selector_fallbacks` provides backup selectors tried in order:

```json
{
  "action": "click",
  "selector": "#submit-btn",
  "selector_fallbacks": [
    "input[type='submit']",
    "button:has-text('Submit')",
    "[data-testid='submit-btn']"
  ]
}
```

Resolution order:
1. Try `#submit-btn`
2. If not found, try `input[type='submit']`
3. If not found, try `button:has-text('Submit')`
4. If not found, try `[data-testid='submit-btn']`
5. If ALL fail and `optional: true` → skip step
6. If ALL fail and `optional: false` → `ELEMENT_NOT_FOUND` error

## Best Practices

- **Prefer `data-testid`** or stable CSS class names over auto-generated IDs
- **Always provide fallbacks** for critical steps (submit, upload)
- **Use XPath** only when CSS cannot express the relationship
- **Avoid brittle selectors** like `div:nth-child(3) > input`
- **Template variables** work in selectors: `[name='{{field_name}}']` — variables are escaped to prevent injection
