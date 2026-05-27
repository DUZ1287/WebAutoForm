"""PII redaction using compiled regex patterns for email, phone, and ID numbers."""

from __future__ import annotations

import re

_EMAIL = re.compile(r"[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}")

_PHONE = re.compile(
    r"(?<!\d)" r"(\+?\d{1,3}[\s\-]?)?" r"(\(?\d{2,4}\)?[\s\-]?)?" r"\d{3,4}[\s\-]?\d{4}" r"(?!\d)"
)

_CN_ID = re.compile(r"\b\d{17}[\dXx]\b")

_SSN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")

_PATTERNS = [_EMAIL, _CN_ID, _SSN, _PHONE]


def redact_text(text: str) -> str:
    """Replace PII occurrences in *text* with '***'."""
    result = text
    for pattern in _PATTERNS:
        result = pattern.sub("***", result)
    return result


def redact_value_for_log(value: str | None, pii_redact: bool) -> str:
    """Return '<redacted>' when *pii_redact* is True, otherwise return raw value."""
    if pii_redact:
        return "<redacted>"
    return value if value is not None else ""
