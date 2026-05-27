"""Tests for wait action."""

import time
from unittest.mock import MagicMock

from web_auto_form.actions.base import ActionContext
from web_auto_form.actions.wait import run_wait
from web_auto_form.models import OptionsConfig, StepConfig


class TestWaitAction:
    def test_wait_timeout(self):
        page = MagicMock()
        step = StepConfig(action="wait", type="timeout", value="100")
        ctx = ActionContext(page=page, step=step, options=OptionsConfig(), step_index=0)
        start = time.monotonic()
        result = run_wait(ctx)
        elapsed = time.monotonic() - start
        assert result.status == "ok"
        assert elapsed >= 0.09

    def test_wait_navigation(self):
        page = MagicMock()
        step = StepConfig(action="wait", type="navigation", timeout_ms=5000)
        ctx = ActionContext(page=page, step=step, options=OptionsConfig(), step_index=0)
        result = run_wait(ctx)
        assert result.status == "ok"
        page.wait_for_load_state.assert_called_once()

    def test_wait_function(self):
        page = MagicMock()
        step = StepConfig(action="wait", type="function", value="() => true")
        ctx = ActionContext(page=page, step=step, options=OptionsConfig(), step_index=0)
        result = run_wait(ctx)
        assert result.status == "ok"
        page.wait_for_function.assert_called_once()
