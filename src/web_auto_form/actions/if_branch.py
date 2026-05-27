"""If action: conditional branching based on element state or value."""

from __future__ import annotations

import logging
import re

from .base import ActionContext, StepResult, timed

logger = logging.getLogger(__name__)


def evaluate_condition(ctx: ActionContext) -> bool:
    """Evaluate the condition of an 'if' step and return True/False."""
    cond = ctx.step.condition
    if cond is None:
        return False

    from ..selectors import resolve_selector

    resolved = resolve_selector(cond.selector)
    loc = ctx.page.locator(resolved).first  # type: ignore[union-attr]

    # Value-based comparison takes precedence
    if cond.operator is not None:
        if cond.attribute == "textContent":
            actual = loc.text_content() or ""
        elif cond.attribute == "value":
            actual = loc.input_value()
        else:
            actual = loc.get_attribute(cond.attribute) or ""

        expected = cond.expected_value or ""

        if cond.operator == "eq":
            return actual == expected
        if cond.operator == "ne":
            return actual != expected
        if cond.operator == "contains":
            return expected in actual
        if cond.operator == "matches_regex":
            return bool(re.search(expected, actual))
        return False

    # State-based check
    state = cond.state or "exist"
    if state == "exist":
        return loc.count() > 0
    if state == "not_exist":
        return loc.count() == 0
    if state == "visible":
        return loc.is_visible()
    if state == "hidden":
        return not loc.is_visible()
    if state == "checked":
        return loc.is_checked()

    return False


@timed
def run_if(ctx: ActionContext) -> StepResult:
    """Execute if/else branching — actual step execution is handled by the runner."""
    return StepResult(step_index=ctx.step_index, action="if", status="ok")
