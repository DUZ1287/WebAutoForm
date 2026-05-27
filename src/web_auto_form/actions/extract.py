"""Extract action: extract text, attributes, or innerHTML from an element."""

from __future__ import annotations

from .base import ActionContext, StepResult, timed


@timed
def run_extract(ctx: ActionContext) -> StepResult:
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
            action="extract",
            status="failed",
            error="element not found",
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
