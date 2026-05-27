"""End-to-end integration tests using a local mock HTTP server."""

import pytest

from web_auto_form import run


@pytest.mark.skipif(
    "not config.getoption('--run-integration', default=False)",
    reason="Integration tests require --run-integration flag",
)
class TestIntegration:
    """Integration tests that launch a real browser against a local form.

    Run with: pytest --run-integration -v
    """

    def test_basic_form_fill(self, mock_server: str):
        config = {
            "url": mock_server,
            "consent_statement": "Integration test.",
            "steps": [
                {
                    "action": "wait",
                    "selector": "form#application",
                    "type": "element",
                    "timeout_ms": 5000,
                },
                {"action": "fill", "selector": "#fullname", "value": "Test User"},
                {"action": "fill", "selector": "input[name='email']", "value": "test@example.com"},
                {"action": "select", "selector": "#position", "value": "eng"},
                {"action": "check", "selector": "#agree-terms", "value": "true"},
                {"action": "click", "selector": "#submit-btn"},
                {
                    "action": "wait",
                    "selector": ".success-message",
                    "type": "element",
                    "timeout_ms": 5000,
                },
            ],
            "extract_schema": {
                "fields": [
                    {"name": "confirmation", "selector": ".success-message", "attribute": "text"},
                    {"name": "app_id", "selector": ".app-id", "attribute": "text"},
                ],
            },
            "options": {"headless": True, "step_delay_ms": 100},
        }
        result = run(config)
        assert result["status"] == "success"
        assert result["extracted"]["confirmation"] == "Application submitted!"
        assert result["extracted"]["app_id"] == "APP-2026-001"

    def test_optional_step_skipped(self, mock_server: str):
        config = {
            "url": mock_server,
            "consent_statement": "Integration test.",
            "steps": [
                {
                    "action": "wait",
                    "selector": "form#application",
                    "type": "element",
                    "timeout_ms": 5000,
                },
                {
                    "action": "fill",
                    "selector": "#nonexistent",
                    "value": "x",
                    "optional": True,
                    "on_skip": "log",
                    "timeout_ms": 1000,
                },
                {"action": "fill", "selector": "#fullname", "value": "OK"},
            ],
            "options": {"headless": True, "step_delay_ms": 100},
        }
        result = run(config)
        assert result["status"] == "success"
        assert result["steps_skipped"] == 1

    def test_conditional_branch(self, mock_server: str):
        config = {
            "url": mock_server,
            "consent_statement": "Integration test.",
            "steps": [
                {
                    "action": "wait",
                    "selector": "form#application",
                    "type": "element",
                    "timeout_ms": 5000,
                },
                {
                    "action": "if",
                    "condition": {"selector": "#has_experience", "state": "checked"},
                    "then": [
                        {"action": "fill", "selector": "#years_experience", "value": "3"},
                    ],
                    "else": [
                        {"action": "fill", "selector": "#fullname", "value": "Fresh Grad"},
                    ],
                },
            ],
            "options": {"headless": True, "step_delay_ms": 100},
        }
        result = run(config)
        assert result["status"] == "success"
