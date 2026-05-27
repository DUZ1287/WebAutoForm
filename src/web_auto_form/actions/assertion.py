"""Assert action: verify element state (exist, visible, checked, etc.)."""

from __future__ import annotations

import logging

from .base import ActionContext, StepResult, timed

logger = logging.getLogger(__name__)


def _check_state(page: object, selector: str, state: str, timeout_ms: int) -> bool:
    """Return True if the element matches the expected state."""
    from ..selectors import resolve_selector

    resolved = resolve_selector(selector)
    loc = page.locator(resolved).first  # type: ignore[attr-defined,union-attr]

    try:
        if state == "exist":
            loc.wait_for(state="attached", timeout=timeout_ms)
            return True
        if state == "not_exist":
            loc.wait_for(state="detached", timeout=timeout_ms)
            return True
        if state == "visible":
            loc.wait_for(state="visible", timeout=timeout_ms)
            return True
        if state == "hidden":
            loc.wait_for(state="hidden", timeout=timeout_ms)
            return True
        if state == "checked":
            loc.wait_for(state="attached", timeout=timeout_ms)
            return bool(loc.is_checked())
        if state == "enabled":
            loc.wait_for(state="attached", timeout=timeout_ms)
            return bool(loc.is_enabled())
        if state == "disabled":
            loc.wait_for(state="attached", timeout=timeout_ms)
            return bool(loc.is_disabled())
    except Exception:
        return state in ("not_exist", "hidden")

    return False


@timed
def run_assert(ctx: ActionContext) -> StepResult:
    selector = ctx.step.selector or ""
    state = ctx.step.state
    max_retries = ctx.step.max_retries or ctx.options.max_retries

    for attempt in range(max_retries + 1):
        actual = _check_state(ctx.page, selector, state, ctx.step.timeout_ms)

        if state in ("not_exist", "hidden"):
            passed = actual  # actual=True means element is gone
        else:
            passed = actual

        if passed:
            return StepResult(
                step_index=ctx.step_index,
                action="assert",
                status="ok",
                retries=attempt,
            )

        if attempt < max_retries:
            import time

            time.sleep(ctx.options.step_delay_ms / 1000.0)
            logger.debug("Assert retry %d/%d for step %d", attempt + 1, max_retries, ctx.step_index)

    return StepResult(
        step_index=ctx.step_index,
        action="assert",
        status="failed",
        retries=max_retries,
        error=f"assertion failed: {selector} state={state}",
    )
