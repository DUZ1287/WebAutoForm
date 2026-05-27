"""Tests for click action."""

from unittest.mock import MagicMock

from web_auto_form.actions.base import ActionContext
from web_auto_form.actions.click import run_click
from web_auto_form.models import OptionsConfig, StepConfig


class TestClickAction:
    def test_click_success(self):
        page = MagicMock()
        loc = MagicMock()
        page.locator.return_value.first = loc
        loc.wait_for = MagicMock()
        loc.count.return_value = 1

        step = StepConfig(action="click", selector="#btn")
        ctx = ActionContext(page=page, step=step, options=OptionsConfig(), step_index=0)
        result = run_click(ctx)
        assert result.status == "ok"
        loc.click.assert_called_once()

    def test_click_element_not_found(self):
        page = MagicMock()
        loc = MagicMock()
        page.locator.return_value.first = loc
        loc.wait_for.side_effect = Exception("timeout")
        loc.count.return_value = 0

        step = StepConfig(action="click", selector="#missing")
        ctx = ActionContext(page=page, step=step, options=OptionsConfig(), step_index=0)
        result = run_click(ctx)
        assert result.status == "failed"
