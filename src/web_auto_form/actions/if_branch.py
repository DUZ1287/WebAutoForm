"""If action: conditional branching based on element state or value."""

from __future__ import annotations

import logging
import re

from ..selectors import normalize_selector, render_locator, resolve_locator
from .base import ActionContext, StepResult, timed

logger = logging.getLogger(__name__)


def evaluate_condition(ctx: ActionContext) -> bool:
    """Evaluate the condition of an 'if' step and return True/False."""
    cond = ctx.step.condition
    if cond is None:
        return False

    # The condition selector arrives unrendered (see `Runner._render_step`), so
    # it goes through the same normalize → render → resolve path as any other
    # locator and gets the same escaping guarantees.
    spec = render_locator(normalize_selector(cond.selector), ctx.data)
    loc = resolve_locator(ctx.page, spec).first

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
