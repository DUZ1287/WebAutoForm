"""Select action: choose an option from a dropdown."""

from __future__ import annotations

from .base import ActionContext, StepResult, timed


@timed
def run_select(ctx: ActionContext) -> StepResult:
    from ..selectors import find_element

    loc = find_element(
        ctx.page, ctx.step.selector or "",
        ctx.step.selector_fallbacks, ctx.step.selector_type, ctx.step.timeout_ms,
    )
    if loc is None:
        return StepResult(
            step_index=ctx.step_index, action="select", status="failed",
            error="element not found",
        )
    loc.select_option(label=ctx.step.value, timeout=ctx.step.timeout_ms)
    return StepResult(step_index=ctx.step_index, action="select", status="ok")
