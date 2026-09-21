"""Shared types for action modules.

Contract for every action handler:

* Run **exactly one attempt** and return a :class:`StepResult`. Do not retry,
  do not loop, do not decide abort/continue/retry — the Runner owns all of that.
* On failure, return a result built with :func:`failed` so the failure carries a
  machine-readable :class:`~web_auto_form.errors.ErrorCode`.
* Let unexpected exceptions propagate; the Runner's exception boundary converts
  them into structured failures.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable, Literal

from playwright.sync_api import Page

from ..errors import ErrorCode, ErrorInfo
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
    error_code: str | None = None
    retryable: bool = False
    diagnostics: dict | None = None


@dataclass
class ActionContext:
    """Context passed to every action function."""

    page: Page
    step: StepConfig
    options: OptionsConfig
    step_index: int
    data: dict[str, Any] = field(default_factory=dict)
    #: Milliseconds left in the workflow budget when this attempt started.
    #: Actions that can block for an author-chosen duration (see `wait
    #: type=timeout`) must clamp to this rather than overrun the workflow.
    remaining_budget_ms: int | None = None


def failed(step_index: int, action: str, code: ErrorCode, message: str) -> StepResult:
    """Build a failed :class:`StepResult` from a structured error classification."""
    info = ErrorInfo(code, message)
    return StepResult(
        step_index=step_index,
        action=action,
        status="failed",
        error=info.message,
        error_code=info.code.value,
        retryable=info.retryable,
    )


def timed(fn: Callable[[ActionContext], StepResult]) -> Callable[[ActionContext], StepResult]:
    """Decorator to measure execution time of an action function."""
    import functools

    @functools.wraps(fn)
    def wrapper(ctx: ActionContext) -> StepResult:
        start = time.monotonic()
        result = fn(ctx)
        result.duration_ms = round((time.monotonic() - start) * 1000, 2)
        return result

    return wrapper
