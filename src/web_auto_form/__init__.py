"""web_auto_form — Browser automation for form filling, submission, and data extraction."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import WebAutoFormConfig
from .runner import Runner

__version__ = "0.1.0"


def run(config: dict[str, Any]) -> dict[str, Any]:
    """Execute a web_auto_form configuration from a dict.

    Args:
        config: A dict matching the web_auto_form input schema.

    Returns:
        A dict with status, results, extracted data, screenshots, and errors.
    """
    parsed = WebAutoFormConfig(**config)
    runner = Runner(parsed)
    return runner.run()


def run_from_path(path: str) -> dict[str, Any]:
    """Load a JSON config file and execute it.

    Args:
        path: Path to a JSON configuration file.

    Returns:
        A dict with status, results, extracted data, screenshots, and errors.
    """
    text = Path(path).read_text(encoding="utf-8")
    config = json.loads(text)
    return run(config)
