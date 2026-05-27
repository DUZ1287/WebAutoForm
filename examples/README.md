# Examples

## job_application.json

Full-featured example demonstrating:
- Template variables (`{{user.name}}`, `{{user.email}}`)
- Selector fallbacks for resilient element targeting
- Conditional branching (`if` checked → fill experience fields)
- File upload from local path
- Assertions with retry (`assert success-message visible, retry 3x`)
- Structured extraction with per-field PII redaction control

```bash
web_auto_form run examples/job_application.json --no-headless --debug
```

## google_form.json

Minimal example for Google Forms-style pages:
- Simple fill + click flow
- Navigation wait after submit

```bash
web_auto_form run examples/google_form.json
```

## conditional_form.json

Showcases advanced conditional logic:
- Value-based `if` condition (compare element attribute to expected value)
- Nested `if`/`else` (2 levels deep)
- Multiple assertions with different `on_fail` strategies

```bash
web_auto_form run examples/conditional_form.json --debug
```
