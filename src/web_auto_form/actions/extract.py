"""Extract action: extract text, attributes, or innerHTML from an element."""

from __future__ import annotations

from ..errors import ErrorCode
from ..selectors import build_locator_chain, find_locator
from .base import ActionContext, StepResult, failed, timed


@timed
def run_extract(ctx: ActionContext) -> StepResult:
    loc = find_locator(ctx.page, build_locator_chain(ctx.step), ctx.step.timeout_ms)
    if loc is None:
        return failed(
            ctx.step_index, ctx.step.action, ErrorCode.ELEMENT_NOT_FOUND, "element not found"
        )

    attr = ctx.step.value or "text"
    if attr == "text":
        content = loc.text_content() or ""
    elif attr == "innerHTML":
        content = loc.inner_html()
    elif attr == "value":
        content = loc.input_value()
    else:
        content = loc.get_attribute(attr) or ""

    return StepResult(
        step_index=ctx.step_index,
        action="extract",
        status="ok",
        value=content,
    )
