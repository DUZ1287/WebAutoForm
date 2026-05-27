"""Shared types for action modules."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Literal

from playwright.sync_api import Page

from ..models import OptionsConfig, StepConfig


@dataclass
class StepResult:
    """Result of executing a single step."""

    step_index: int
    action: str
    status: Literal["ok", "skipped", "failed"]
    duration_ms: float = 0.0
    retries: int = 0
    screenshot: str | None = None
    value: str | None = None
    error: str | None = None
    diagnostics: dict | None = None


@dataclass
class ActionContext:
    """Context passed to every action function."""

    page: Page
    step: StepConfig
    options: OptionsConfig
    step_index: int
    data: dict[str, Any] = field(default_factory=dict)


def timed(fn: Any) -> Any:
    """Decorator to measure execution time of an action function."""
    import functools

    @functools.wraps(fn)
    def wrapper(ctx: ActionContext) -> StepResult:
        start = time.monotonic()
        result = fn(ctx)
        result.duration_ms = round((time.monotonic() - start) * 1000, 2)
        return result

    return wrapper
