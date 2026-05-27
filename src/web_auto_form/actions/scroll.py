"""Scroll action: scroll the page up or down."""

from __future__ import annotations

from .base import ActionContext, StepResult, timed


@timed
def run_scroll(ctx: ActionContext) -> StepResult:
    value = (ctx.step.value or "down").lower()

    if value in ("up", "down"):
        delta = -500 if value == "up" else 500
        ctx.page.mouse.wheel(0, delta)
    else:
        try:
            pixels = int(value)
            ctx.page.mouse.wheel(0, pixels)
        except ValueError:
            return StepResult(
                step_index=ctx.step_index,
                action="scroll",
                status="failed",
                error=f"invalid scroll value: {value!r}",
            )

    return StepResult(step_index=ctx.step_index, action="scroll", status="ok")
