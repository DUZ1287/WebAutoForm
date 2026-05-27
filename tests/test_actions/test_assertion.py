"""Tests for assert action."""

from unittest.mock import MagicMock

from web_auto_form.actions.assertion import run_assert
from web_auto_form.actions.base import ActionContext
from web_auto_form.models import OptionsConfig, StepConfig


class TestAssertAction:
    def test_assert_exist_passes(self):
        page = MagicMock()
        loc = MagicMock()
        page.locator.return_value.first = loc
        loc.wait_for = MagicMock()

        step = StepConfig(action="assert", selector="#el", state="exist")
        ctx = ActionContext(page=page, step=step, options=OptionsConfig(), step_index=0)
        result = run_assert(ctx)
        assert result.status == "ok"

    def test_assert_not_exist_passes_when_gone(self):
        page = MagicMock()
        loc = MagicMock()
        page.locator.return_value.first = loc
        loc.wait_for = MagicMock()

        step = StepConfig(action="assert", selector="#el", state="not_exist")
        ctx = ActionContext(page=page, step=step, options=OptionsConfig(), step_index=0)
        result = run_assert(ctx)
        assert result.status == "ok"

    def test_assert_visible_retries_and_fails(self):
        page = MagicMock()
        loc = MagicMock()
        page.locator.return_value.first = loc
        loc.wait_for.side_effect = Exception("timeout")

        step = StepConfig(action="assert", selector="#el", state="visible", on_fail="abort")
        opts = OptionsConfig(max_retries=1)
        ctx = ActionContext(page=page, step=step, options=opts, step_index=0)
        result = run_assert(ctx)
        assert result.status == "failed"
        assert result.retries == 1
