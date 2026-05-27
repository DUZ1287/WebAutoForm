"""Tests for Pydantic model validation."""

import pytest
from pydantic import ValidationError

from web_auto_form.models import (
    OptionsConfig,
    StepConfig,
    WebAutoFormConfig,
)


class TestStepConfig:
    def test_minimal_step(self):
        step = StepConfig(action="click", selector="#btn")
        assert step.action == "click"
        assert step.timeout_ms == 5000
        assert step.optional is False

    def test_wait_timeout_requires_numeric_value(self):
        with pytest.raises(ValidationError, match="numeric string"):
            StepConfig(action="wait", type="timeout", value="abc")

    def test_wait_timeout_valid(self):
        step = StepConfig(action="wait", type="timeout", value="3000")
        assert step.value == "3000"

    def test_wait_function_requires_value(self):
        with pytest.raises(ValidationError, match="non-empty value"):
            StepConfig(action="wait", type="function", value=None)

    def test_if_requires_condition_and_then(self):
        with pytest.raises(ValidationError):
            StepConfig(action="if")

    def test_navigate_requires_value(self):
        with pytest.raises(ValidationError):
            StepConfig(action="navigate")

    def test_fill_requires_selector(self):
        with pytest.raises(ValidationError):
            StepConfig(action="fill")


class TestWebAutoFormConfig:
    def test_minimal_config(self):
        cfg = WebAutoFormConfig(
            url="https://example.com",
            consent_statement="test",
            steps=[StepConfig(action="navigate", value="https://example.com")],
        )
        assert cfg.url == "https://example.com"
        assert len(cfg.steps) == 1

    def test_empty_steps_rejected(self):
        with pytest.raises(ValidationError):
            WebAutoFormConfig(
                url="https://example.com",
                consent_statement="test",
                steps=[],
            )

    def test_over_50_steps_rejected(self):
        steps = [StepConfig(action="click", selector="#x") for _ in range(51)]
        with pytest.raises(ValidationError):
            WebAutoFormConfig(
                url="https://example.com",
                consent_statement="test",
                steps=steps,
            )


class TestOptionsConfig:
    def test_defaults(self):
        opts = OptionsConfig()
        assert opts.headless is True
        assert opts.step_delay_ms == 500
        assert opts.redact_pii is True
        assert opts.sandbox is True

    def test_step_delay_bounds(self):
        with pytest.raises(ValidationError):
            OptionsConfig(step_delay_ms=50)  # below minimum 100
