"""Handle dialog action: accept or dismiss browser dialogs."""

from __future__ import annotations

from .base import ActionContext, StepResult, timed


@timed
def run_handle_dialog(ctx: ActionContext) -> StepResult:
    action_type = (ctx.step.value or "accept").lower()

    def _handler(dialog: object) -> None:
        if action_type == "accept":
            dialog.accept()  # type: ignore[attr-defined]
        else:
            dialog.dismiss()  # type: ignore[attr-defined]
        ctx.page.remove_listener("dialog", _handler)

    ctx.page.on("dialog", _handler)
    return StepResult(step_index=ctx.step_index, action="handle_dialog", status="ok")
