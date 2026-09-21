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


@pytest.mark.skipif(
    "not config.getoption('--run-integration', default=False)",
    reason="Integration tests require --run-integration flag",
)
class TestReliabilityIntegration:
    """Real-browser failure classification and containment.

    Playwright's actual exception messages are what ``classify_exception`` keys
    off, so these are the only tests that can validate the classification.
    """

    def _run(self, url: str, steps: list, **options) -> dict:
        opts = {"headless": True, "step_delay_ms": 100}
        opts.update(options)
        return run(
            {
                "url": url,
                "consent_statement": "Integration test.",
                "steps": steps,
                "options": opts,
            }
        )

    def test_element_not_found_carries_code_and_diagnostics(self, mock_server: str):
        result = self._run(
            mock_server,
            [{"action": "click", "selector": "#definitely-not-here", "timeout_ms": 1000}],
        )
        step = result["results"][0]

        assert result["status"] == "failed"
        assert step["error_code"] == "ELEMENT_NOT_FOUND"
        assert step["retryable"] is False

        elements = step["diagnostics"]["form_elements"]
        assert elements, "diagnostics.form_elements must list the page's form elements"
        assert any(e["id"] == "fullname" for e in elements)

    def test_hidden_element_is_not_visible(self, mock_server: str):
        # #years_experience sits inside a display:none container.
        result = self._run(
            mock_server,
            [{"action": "click", "selector": "#years_experience", "timeout_ms": 2000}],
        )
        assert result["results"][0]["error_code"] == "ELEMENT_NOT_VISIBLE"
        assert result["results"][0]["retryable"] is True

    def test_disabled_element_is_not_interactable(self, mock_server: str):
        result = self._run(
            mock_server,
            [{"action": "click", "selector": "#disabled-btn", "timeout_ms": 2000}],
        )
        assert result["results"][0]["error_code"] == "ELEMENT_NOT_INTERACTABLE"

    def test_invalid_selector_is_not_reported_as_not_found(self, mock_server: str):
        result = self._run(
            mock_server,
            [{"action": "click", "selector": ">>>", "timeout_ms": 1000}],
        )
        step = result["results"][0]
        assert step["error_code"] == "INVALID_SELECTOR"
        assert step["retryable"] is False

    def test_assert_not_exist_fails_on_present_element(self, mock_server: str):
        result = self._run(
            mock_server,
            [
                {
                    "action": "assert",
                    "selector": "#fullname",
                    "state": "not_exist",
                    "timeout_ms": 1000,
                }
            ],
        )
        assert result["results"][0]["error_code"] == "ASSERTION_FAILED"

    def test_retries_equal_initial_attempt_plus_max_retries(self, mock_server: str):
        result = self._run(
            mock_server,
            [
                {
                    "action": "click",
                    "selector": "#nope",
                    "on_fail": "retry",
                    "max_retries": 2,
                    "timeout_ms": 300,
                }
            ],
        )
        assert result["results"][0]["retries"] == 2
        assert result["aborted"] is True

    def test_abort_skips_remaining_steps(self, mock_server: str):
        result = self._run(
            mock_server,
            [
                {
                    "action": "wait",
                    "selector": "form#application",
                    "type": "element",
                    "timeout_ms": 5000,
                },
                {"action": "click", "selector": "#nope", "timeout_ms": 500},
                {"action": "fill", "selector": "#fullname", "value": "unreachable"},
            ],
        )
        assert result["aborted"] is True
        assert result["status"] == "failed"
        assert len(result["results"]) == 2, "the step after the abort must not run"

    def test_abort_inside_if_branch_propagates_to_top_level(self, mock_server: str):
        result = self._run(
            mock_server,
            [
                {
                    "action": "if",
                    "condition": {"selector": "#has_experience", "state": "exist"},
                    "then": [
                        {"action": "click", "selector": "#nope", "timeout_ms": 500},
                        {"action": "fill", "selector": "#fullname", "value": "unreachable"},
                    ],
                },
                {"action": "fill", "selector": "#fullname", "value": "also unreachable"},
            ],
        )
        assert result["aborted"] is True
        assert not any(r["action"] == "fill" for r in result["results"])

    def test_optional_failure_keeps_workflow_successful(self, mock_server: str):
        result = self._run(
            mock_server,
            [
                {"action": "click", "selector": "#nope", "optional": True, "timeout_ms": 500},
                {"action": "fill", "selector": "#fullname", "value": "OK"},
            ],
        )
        assert result["status"] == "success"
        assert result["steps_skipped"] == 1

    def test_select_accepts_both_value_and_label(self, mock_server: str):
        for target in ("eng", "Product Manager"):
            result = self._run(
                mock_server,
                [{"action": "select", "selector": "#position", "value": target}],
            )
            assert result["status"] == "success", f"{target!r} failed: {result['errors']}"
