"""Select action: choose an option from a dropdown."""

from __future__ import annotations

from ..errors import ErrorCode
from ..selectors import build_locator_chain, find_locator
from .base import ActionContext, StepResult, failed, timed


@timed
def run_select(ctx: ActionContext) -> StepResult:
    loc = find_locator(ctx.page, build_locator_chain(ctx.step), ctx.step.timeout_ms)
    if loc is None:
        return failed(
            ctx.step_index, ctx.step.action, ErrorCode.ELEMENT_NOT_FOUND, "element not found"
        )
    # `value` is documented as "option text OR value attribute". Playwright
    # accepts both criteria in one call, so <option value="eng">Software
    # Engineer</option> matches either value="eng" or label="eng".
    loc.select_option(value=ctx.step.value, label=ctx.step.value, timeout=ctx.step.timeout_ms)
    return StepResult(step_index=ctx.step_index, action="select", status="ok")
