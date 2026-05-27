"""Wait action: wait for element, navigation, timeout, or JS condition."""

from __future__ import annotations

import logging
import time

from playwright.sync_api import TimeoutError as PwTimeout

from .base import ActionContext, StepResult, timed

logger = logging.getLogger(__name__)


@timed
def run_wait(ctx: ActionContext) -> StepResult:
    wait_type = ctx.step.type

    if wait_type == "timeout":
        ms = int(ctx.step.value or "0")
        time.sleep(ms / 1000.0)
        return StepResult(step_index=ctx.step_index, action="wait", status="ok")

    if wait_type == "navigation":
        try:
            ctx.page.wait_for_load_state("domcontentloaded", timeout=ctx.step.timeout_ms)
        except PwTimeout:
            return StepResult(
                step_index=ctx.step_index,
                action="wait",
                status="failed",
                error="navigation wait timed out",
            )
        return StepResult(step_index=ctx.step_index, action="wait", status="ok")

    if wait_type == "function":
        js_expr = ctx.step.value
        if not js_expr:
            return StepResult(
                step_index=ctx.step_index,
                action="wait",
                status="failed",
                error="wait type=function requires a JS expression in value",
            )
        try:
            ctx.page.wait_for_function(js_expr, timeout=ctx.step.timeout_ms)
        except PwTimeout:
            return StepResult(
                step_index=ctx.step_index,
                action="wait",
                status="failed",
                error="wait type=function timed out",
            )
        return StepResult(step_index=ctx.step_index, action="wait", status="ok")

    # type == "element" (default)
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
            action="wait",
            status="failed",
            error="element not found within timeout",
        )
    return StepResult(step_index=ctx.step_index, action="wait", status="ok")
