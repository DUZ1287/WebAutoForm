"""Action registry mapping action names to handler functions."""

from __future__ import annotations

from typing import Callable

from .assertion import run_assert
from .base import ActionContext, StepResult
from .check import run_check
from .click import run_click
from .extract import run_extract
from .fill import run_fill
from .handle_dialog import run_handle_dialog
from .if_branch import run_if
from .navigate import run_navigate
from .press_key import run_press_key
from .scroll import run_scroll
from .select import run_select
from .upload import run_upload
from .wait import run_wait

ACTION_REGISTRY: dict[str, Callable[[ActionContext], StepResult]] = {
    "navigate": run_navigate,
    "fill": run_fill,
    "select": run_select,
    "check": run_check,
    "click": run_click,
    "upload": run_upload,
    "wait": run_wait,
    "scroll": run_scroll,
    "extract": run_extract,
    "press_key": run_press_key,
    "handle_dialog": run_handle_dialog,
    "assert": run_assert,
}

__all__ = ["ACTION_REGISTRY", "ActionContext", "StepResult"]
