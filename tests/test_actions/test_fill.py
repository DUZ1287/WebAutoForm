"""Tests for fill action."""

from unittest.mock import MagicMock

from web_auto_form.actions.base import ActionContext
from web_auto_form.actions.fill import run_fill
from web_auto_form.models import OptionsConfig, StepConfig


def _make_ctx(selector="#input", value="hello") -> ActionContext:
    page = MagicMock()
    loc = MagicMock()
    page.locator.return_value.first = loc
    loc.wait_for = MagicMock()
    loc.count.return_value = 1
    loc.fill = MagicMock()

    step = StepConfig(action="fill", selector=selector, value=value)
    return ActionContext(
        page=page, step=step, options=OptionsConfig(), step_index=0,
    )


class TestFillAction:
    def test_fill_success(self):
        ctx = _make_ctx()
        result = run_fill(ctx)
        assert result.status == "ok"
        ctx.page.locator.return_value.first.fill.assert_called_once()

    def test_fill_element_not_found(self):
        page = MagicMock()
        loc = MagicMock()
        page.locator.return_value.first = loc
        loc.wait_for.side_effect = Exception("timeout")
        loc.count.return_value = 0

        step = StepConfig(action="fill", selector="#missing", value="x")
        ctx = ActionContext(page=page, step=step, options=OptionsConfig(), step_index=0)
        result = run_fill(ctx)
        assert result.status == "failed"
        assert "not found" in result.error
