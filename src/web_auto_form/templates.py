"""Template variable rendering for {{key}} placeholders with dot-notation support."""

from __future__ import annotations

import re
from typing import Any

_PATTERN = re.compile(r"\{\{([^}]+)\}\}")


class TemplateSecurityError(ValueError):
    """A template placeholder sits in a position that cannot be escaped safely.

    Raised before any browser interaction, and surfaced as ``TEMPLATE_ERROR``.
    """


def has_placeholder(template: str | None) -> bool:
    """Whether *template* contains a ``{{...}}`` placeholder.

    Callers use this to decide policy from the **configuration** rather than from
    a rendered string: which rule applies must never be influenced by the data
    being substituted.
    """
    if not template:
        return False
    return _PATTERN.search(template) is not None


def _lookup(data: dict[str, Any], key: str) -> str:
    """Resolve a dot-notation key like 'user.name' against a nested dict."""
    parts = key.split(".")
    current: Any = data
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return ""
    return str(current)


def render(template: str, data: dict[str, Any]) -> str:
    """Replace all {{key}} placeholders in *template* using *data*."""

    def _replace(match: re.Match[str]) -> str:
        key = match.group(1).strip()
        return _lookup(data, key)

    return _PATTERN.sub(_replace, template)


def render_dict(obj: Any, data: dict[str, Any]) -> Any:
    """Recursively render template variables in all string values of a dict/list."""
    if isinstance(obj, str):
        return render(obj, data)
    if isinstance(obj, dict):
        return {k: render_dict(v, data) for k, v in obj.items()}
    if isinstance(obj, list):
        return [render_dict(item, data) for item in obj]
    return obj
