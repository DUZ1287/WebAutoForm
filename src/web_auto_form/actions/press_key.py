"""Press key action: press a keyboard key."""

from __future__ import annotations

from .base import ActionContext, StepResult, timed


@timed
def run_press_key(ctx: ActionContext) -> StepResult:
    key = ctx.step.value or "Enter"
    ctx.page.keyboard.press(key)
    return StepResult(step_index=ctx.step_index, action="press_key", status="ok")
