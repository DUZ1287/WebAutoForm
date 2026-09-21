"""Fill action: type text into an input field."""

from __future__ import annotations

from ..errors import ErrorCode
from ..selectors import build_locator_chain, find_locator
from .base import ActionContext, StepResult, failed, timed


@timed
def run_fill(ctx: ActionContext) -> StepResult:
    loc = find_locator(ctx.page, build_locator_chain(ctx.step), ctx.step.timeout_ms)
    if loc is None:
        return failed(
            ctx.step_index, ctx.step.action, ErrorCode.ELEMENT_NOT_FOUND, "element not found"
        )
    loc.fill(ctx.step.value or "", timeout=ctx.step.timeout_ms)
    return StepResult(step_index=ctx.step_index, action="fill", status="ok")
