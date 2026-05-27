"""Check action: check or uncheck a checkbox / radio button."""

from __future__ import annotations

from .base import ActionContext, StepResult, timed


@timed
def run_check(ctx: ActionContext) -> StepResult:
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
            action="check",
            status="failed",
            error="element not found",
        )
    should_check = (ctx.step.value or "true").lower() == "true"
    if should_check:
        loc.check(timeout=ctx.step.timeout_ms)
    else:
        loc.uncheck(timeout=ctx.step.timeout_ms)
    return StepResult(step_index=ctx.step_index, action="check", status="ok")
