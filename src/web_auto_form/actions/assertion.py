"""Assert action: verify element state (exist, visible, checked, etc.).

The handler performs **exactly one** check and reports ``ASSERTION_FAILED`` on a
miss. It does not loop and does not decide abort/continue/retry — retry belongs
to the Runner, driven by ``on_fail`` / ``max_retries`` / ``retry_on`` like every
other action. See ``runner._should_retry`` and ``runner._apply_failure_policy``.
"""

from __future__ import annotations

import logging

from playwright.sync_api import Locator

from ..errors import ErrorCode
from ..selectors import build_locator_chain, describe_locator, resolve_locator
from .base import ActionContext, StepResult, failed, timed

logger = logging.getLogger(__name__)


def _check_state(loc: Locator, state: str, timeout_ms: int) -> bool:
    """Return True if *loc* matches the expected state."""
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
    except Exception as exc:
        # Every state expresses "the element should be X"; a timeout means it
        # never became X. That includes the negative states — a timeout waiting
        # for "detached"/"hidden" means the element is still on the page, so
        # `not_exist` / `hidden` have *not* been satisfied.
        logger.debug("assert state check raised: %s", exc)

    return False


@timed
def run_assert(ctx: ActionContext) -> StepResult:
    """Verify element state. One check per candidate, no retry loop of its own."""
    chain = build_locator_chain(ctx.step)
    state = ctx.step.state

    # Walk the chain rather than using find_locator: a *missing* element is not a
    # lookup failure here — `not_exist` and `hidden` are satisfied by absence.
    for spec in chain:
        loc = resolve_locator(ctx.page, spec).first
        if _check_state(loc, state, ctx.step.timeout_ms):
            return StepResult(step_index=ctx.step_index, action=ctx.step.action, status="ok")

    return failed(
        ctx.step_index,
        ctx.step.action,
        ErrorCode.ASSERTION_FAILED,
        f"assertion failed: {describe_locator(chain[0])} state={state}",
    )
