# PII Redaction

## Overview

web_auto_form redacts personally identifiable information (PII) in two places:

1. **Log output**: `value` fields are printed as `<redacted>` when `options.redact_pii` is `true`
2. **Extracted text**: phone numbers, email addresses, and ID numbers are replaced with `***`

## Global Switch

```json
"options": {
  "redact_pii": true
}
```

When `true` (default), all PII is redacted. When `false`, raw values appear in output.

## Per-Field Override

Individual extract fields can override the global setting:

```json
"extract_schema": {
  "fields": [
    {"name": "app_id", "selector": ".id", "redact": false},
    {"name": "user_email", "selector": ".email", "redact": true}
  ]
}
```

- `redact: true` → always redact this field, regardless of global setting
- `redact: false` → never redact this field (e.g., non-PII like `application_id`)
- `redact` omitted → follow global `options.redact_pii`

## Detected PII Types

| Type | Pattern Example |
| --- | --- |
| Email | `user@example.com` |
| Phone | `+86 138-0000-1234`, `(555) 123-4567` |
| Chinese ID | `110101199001011234` |
| SSN | `123-45-6789` |

## Disabling Redaction

To get raw output, set `redact_pii: false` globally:

```json
"options": {
  "redact_pii": false
}
```

A warning is logged when redaction is disabled.
