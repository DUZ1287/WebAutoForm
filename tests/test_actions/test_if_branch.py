"""Tests for if action condition evaluation."""

from unittest.mock import MagicMock

from web_auto_form.actions.base import ActionContext
from web_auto_form.actions.if_branch import evaluate_condition
from web_auto_form.models import ConditionConfig, OptionsConfig, StepConfig


class TestEvaluateCondition:
    def test_state_exist_when_present(self):
        page = MagicMock()
        loc = MagicMock()
        page.locator.return_value.first = loc
        loc.wait_for = MagicMock()
        loc.count.return_value = 1

        step = StepConfig(
            action="if",
            condition=ConditionConfig(selector="#el", state="exist"),
            then=[StepConfig(action="click", selector="#x")],
        )
        ctx = ActionContext(page=page, step=step, options=OptionsConfig(), step_index=0)
        assert evaluate_condition(ctx) is True

    def test_state_not_exist_when_absent(self):
        page = MagicMock()
        loc = MagicMock()
        page.locator.return_value.first = loc
        loc.count.return_value = 0

        step = StepConfig(
            action="if",
            condition=ConditionConfig(selector="#el", state="not_exist"),
            then=[StepConfig(action="click", selector="#x")],
        )
        ctx = ActionContext(page=page, step=step, options=OptionsConfig(), step_index=0)
        assert evaluate_condition(ctx) is True

    def test_operator_eq(self):
        page = MagicMock()
        loc = MagicMock()
        page.locator.return_value.first = loc
        loc.text_content.return_value = "Approved"

        step = StepConfig(
            action="if",
            condition=ConditionConfig(
                selector=".status", attribute="textContent",
                operator="eq", expected_value="Approved",
            ),
            then=[StepConfig(action="click", selector="#x")],
        )
        ctx = ActionContext(page=page, step=step, options=OptionsConfig(), step_index=0)
        assert evaluate_condition(ctx) is True

    def test_operator_contains(self):
        page = MagicMock()
        loc = MagicMock()
        page.locator.return_value.first = loc
        loc.text_content.return_value = "The application is approved now"

        step = StepConfig(
            action="if",
            condition=ConditionConfig(
                selector=".status", operator="contains", expected_value="approved",
            ),
            then=[StepConfig(action="click", selector="#x")],
        )
        ctx = ActionContext(page=page, step=step, options=OptionsConfig(), step_index=0)
        assert evaluate_condition(ctx) is True

    def test_operator_ne(self):
        page = MagicMock()
        loc = MagicMock()
        page.locator.return_value.first = loc
        loc.text_content.return_value = "Rejected"

        step = StepConfig(
            action="if",
            condition=ConditionConfig(
                selector=".status", operator="ne", expected_value="Approved",
            ),
            then=[StepConfig(action="click", selector="#x")],
        )
        ctx = ActionContext(page=page, step=step, options=OptionsConfig(), step_index=0)
        assert evaluate_condition(ctx) is True
