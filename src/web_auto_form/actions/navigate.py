"""Navigate action: open a URL."""

from __future__ import annotations

from ..errors import ErrorCode
from .base import ActionContext, StepResult, failed, timed


@timed
def run_navigate(ctx: ActionContext) -> StepResult:
    url = ctx.step.value
    if not url:
        # Unreachable via the config schema; kept for direct API callers.
        return failed(
            ctx.step_index,
            ctx.step.action,
            ErrorCode.INTERNAL_ERROR,
            "navigate requires a URL in the value field",
        )
    ctx.page.goto(url, wait_until="domcontentloaded", timeout=ctx.step.timeout_ms)
    return StepResult(step_index=ctx.step_index, action="navigate", status="ok")
