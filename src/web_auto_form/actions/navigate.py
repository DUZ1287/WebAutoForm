"""Navigate action: open a URL."""

from __future__ import annotations

from .base import ActionContext, StepResult, timed


@timed
def run_navigate(ctx: ActionContext) -> StepResult:
    url = ctx.step.value
    if not url:
        return StepResult(
            step_index=ctx.step_index,
            action="navigate",
            status="failed",
            error="navigate requires a URL in the value field",
        )
    ctx.page.goto(url, wait_until="domcontentloaded", timeout=ctx.step.timeout_ms)
    return StepResult(step_index=ctx.step_index, action="navigate", status="ok")
