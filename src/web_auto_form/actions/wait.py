"""Wait action: wait for element, navigation, timeout, or JS condition."""

from __future__ import annotations

import logging
import time

from playwright.sync_api import TimeoutError as PwTimeout

from ..errors import ErrorCode
from ..selectors import build_locator_chain, find_locator
from .base import ActionContext, StepResult, failed, timed

logger = logging.getLogger(__name__)


@timed
def run_wait(ctx: ActionContext) -> StepResult:
    wait_type = ctx.step.type

    if wait_type == "timeout":
        requested = int(ctx.step.value or "0")
        budget = ctx.remaining_budget_ms
        # `value` is author-chosen and has no schema upper bound, so an
        # unconditional sleep could outrun the workflow budget entirely — the
        # budget is only checked between steps and cannot interrupt a sleep.
        # Instead of truncating (which would silently turn a wait into a
        # no-op that still reports success), refuse it.
        if budget is not None and requested > budget:
            return failed(
                ctx.step_index,
                ctx.step.action,
                ErrorCode.TIMEOUT,
                f"wait of {requested}ms exceeds the remaining workflow budget of {budget}ms",
            )
        time.sleep(requested / 1000.0)
        return StepResult(step_index=ctx.step_index, action="wait", status="ok")

    if wait_type == "navigation":
        try:
            ctx.page.wait_for_load_state("domcontentloaded", timeout=ctx.step.timeout_ms)
        except PwTimeout:
            return failed(
                ctx.step_index,
                ctx.step.action,
                ErrorCode.NAVIGATION_FAILED,
                "navigation wait timed out",
            )
        return StepResult(step_index=ctx.step_index, action="wait", status="ok")

    if wait_type == "function":
        js_expr = ctx.step.value
        if not js_expr:
            # Unreachable via the config schema; kept for direct API callers.
            return failed(
                ctx.step_index,
                ctx.step.action,
                ErrorCode.INTERNAL_ERROR,
                "wait type=function requires a JS expression in value",
            )
        try:
            ctx.page.wait_for_function(js_expr, timeout=ctx.step.timeout_ms)
        except PwTimeout:
            return failed(
                ctx.step_index,
                ctx.step.action,
                ErrorCode.TIMEOUT,
                "wait type=function timed out",
            )
        return StepResult(step_index=ctx.step_index, action="wait", status="ok")

    # type == "element" (default)
    loc = find_locator(ctx.page, build_locator_chain(ctx.step), ctx.step.timeout_ms)
    if loc is None:
        return failed(
            ctx.step_index,
            ctx.step.action,
            ErrorCode.ELEMENT_NOT_FOUND,
            "element not found within timeout",
        )
    return StepResult(step_index=ctx.step_index, action="wait", status="ok")
