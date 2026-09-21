"""Click action: click a button, link, or other element."""

from __future__ import annotations

from ..errors import ErrorCode
from ..selectors import build_locator_chain, find_locator
from .base import ActionContext, StepResult, failed, timed


@timed
def run_click(ctx: ActionContext) -> StepResult:
    loc = find_locator(ctx.page, build_locator_chain(ctx.step), ctx.step.timeout_ms)
    if loc is None:
        return failed(
            ctx.step_index, ctx.step.action, ErrorCode.ELEMENT_NOT_FOUND, "element not found"
        )
    loc.click(timeout=ctx.step.timeout_ms)
    return StepResult(step_index=ctx.step_index, action="click", status="ok")
