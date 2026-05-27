"""Fill action: type text into an input field."""

from __future__ import annotations

from .base import ActionContext, StepResult, timed


@timed
def run_fill(ctx: ActionContext) -> StepResult:
    from ..selectors import find_element

    loc = find_element(
        ctx.page,
        ctx.step.selector or "",
        ctx.step.selector_fallbacks,
        ctx.step.selector_type,
        ctx.step.timeout_ms,
    )
    if loc is None:
        return StepResult(
            step_index=ctx.step_index,
            action="fill",
            status="failed",
            error="element not found",
        )
    loc.fill(ctx.step.value or "", timeout=ctx.step.timeout_ms)
    return StepResult(step_index=ctx.step_index, action="fill", status="ok")
