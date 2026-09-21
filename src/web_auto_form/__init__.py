"""web_auto_form — Browser automation for form filling, submission, and data extraction."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .errors import ErrorCode, error_entry, validation_entries
from .models import WebAutoFormConfig
from .runner import Runner, failed_output

__version__ = "0.1.0"


def run(config: dict[str, Any]) -> dict[str, Any]:
    """Execute a web_auto_form configuration from a dict.

    Never raises for a malformed configuration: this is the entry point used by
    the CLI, the MCP server and Agent tool pipelines, where an invalid config is
    an *observation* the caller can act on, not a transport failure.
    ``WebAutoFormConfig(...)`` stays the strict low-level validator for callers
    that want the exception.

    Args:
        config: A dict matching the web_auto_form input schema.

    Returns:
        A dict with status, results, extracted data, screenshots, and errors.
    """
    if not isinstance(config, dict):
        return failed_output(
            [
                error_entry(
                    ErrorCode.CONFIG_VALIDATION_ERROR,
                    f"configuration must be a JSON object, got {type(config).__name__}",
                )
            ]
        )

    try:
        parsed = WebAutoFormConfig(**config)
    except ValidationError as exc:
        return failed_output(validation_entries(exc), config.get("consent_statement"))

    return Runner(parsed).run()


def run_from_path(path: str) -> dict[str, Any]:
    """Load a JSON config file and execute it.

    Args:
        path: Path to a JSON configuration file.

    Returns:
        A dict with status, results, extracted data, screenshots, and errors.
    """
    try:
        text = Path(path).read_text(encoding="utf-8")
        config = json.loads(text)
    except Exception as exc:
        return failed_output(
            [
                error_entry(
                    ErrorCode.CONFIG_VALIDATION_ERROR,
                    f"{type(exc).__name__}: {exc}",
                    field=None,
                )
            ]
        )
    return run(config)
