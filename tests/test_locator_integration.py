"""Real-browser locator behaviour: semantic strategies, injection, resilience.

These complement `tests/test_locators.py`. That file proves the *policy* (which
positions are refused, what the escaper produces); this one proves the browser
actually agrees — and that semantic locators survive the DOM renames which break
brittle selectors. The latter is the baseline the future self-healing phase has
to beat.
"""

from __future__ import annotations

from typing import Any

import pytest

from web_auto_form import run


@pytest.mark.skipif(
    "not config.getoption('--run-integration', default=False)",
    reason="Integration tests require --run-integration flag",
)
class TestLocatorIntegration:
    def _run(
        self,
        url: str,
        steps: list,
        data: dict[str, Any] | None = None,
        extract_schema: dict[str, Any] | None = None,
        **options: Any,
    ) -> dict:
        opts: dict[str, Any] = {"headless": True, "step_delay_ms": 100}
        opts.update(options)
        config: dict[str, Any] = {
            "url": url,
            "consent_statement": "Integration test.",
            "steps": steps,
            "options": opts,
        }
        if data is not None:
            config["data"] = data
        if extract_schema is not None:
            config["extract_schema"] = extract_schema
        return run(config)

    def _fill_via(self, url: str, locator: dict, value: str = "FILLED") -> dict:
        return self._run(
            url,
            [{"action": "fill", "locator": locator, "value": value, "timeout_ms": 2000}],
        )

    # ── Semantic strategies ──────────────────────────────────────────────

    @pytest.mark.parametrize(
        "locator",
        [
            {"strategy": "label", "value": "Email"},
            {"strategy": "placeholder", "value": "Phone number"},
            {"strategy": "testid", "value": "username"},
            {"strategy": "name", "value": "email"},
        ],
    )
    def test_semantic_locators_resolve(self, locator_pages: dict, locator: dict):
        result = self._fill_via(locator_pages["before"], locator)
        assert result["status"] == "success", result["errors"]

    def test_role_locator_resolves(self, locator_pages: dict):
        result = self._run(
            locator_pages["before"],
            [
                {
                    "action": "click",
                    "locator": {"strategy": "role", "role": "button", "name": "Submit"},
                    "timeout_ms": 2000,
                }
            ],
        )
        assert result["status"] == "success", result["errors"]

    def test_role_with_exact_name_resolves(self, locator_pages: dict):
        result = self._run(
            locator_pages["before"],
            [
                {
                    "action": "click",
                    "locator": {
                        "strategy": "role",
                        "role": "button",
                        "name": "Submit",
                        "exact": True,
                    },
                    "timeout_ms": 2000,
                }
            ],
        )
        assert result["status"] == "success", result["errors"]

    def test_attribute_operator_is_honoured(self, locator_pages: dict):
        result = self._fill_via(
            locator_pages["before"],
            {"strategy": "attr", "attr": "name", "op": "^=", "value": "em"},
        )
        assert result["status"] == "success", result["errors"]

    # ── Resilience: the reason semantic locators exist ───────────────────

    def test_semantic_locator_survives_a_dom_rename(self, locator_pages: dict):
        """Ids and classes differ between variants; accessible names do not."""
        locator = {"strategy": "label", "value": "Email"}
        assert self._fill_via(locator_pages["before"], locator)["status"] == "success"
        assert self._fill_via(locator_pages["after"], locator)["status"] == "success"

    def test_brittle_selector_breaks_on_the_same_rename(self, locator_pages: dict):
        """The counterpart: this is what self-healing must eventually fix, and it
        must fail loudly rather than silently matching nothing."""
        brittle = {"strategy": "css", "value": "#a-email"}
        assert self._fill_via(locator_pages["before"], brittle)["status"] == "success"

        after = self._fill_via(locator_pages["after"], brittle)
        assert after["status"] == "failed"
        assert after["results"][0]["error_code"] == "ELEMENT_NOT_FOUND"

    def test_semantic_fallback_rescues_a_brittle_primary(self, locator_pages: dict):
        result = self._run(
            locator_pages["after"],
            [
                {
                    "action": "fill",
                    "locator": {"strategy": "css", "value": "#a-email"},
                    "locator_fallbacks": [
                        {"strategy": "label", "value": "Email"},
                    ],
                    "value": "FILLED",
                    "timeout_ms": 1500,
                }
            ],
        )
        assert result["status"] == "success", result["errors"]

    def test_legacy_fallback_chain_still_works(self, locator_pages: dict):
        result = self._run(
            locator_pages["after"],
            [
                {
                    "action": "fill",
                    "selector": "#a-email",
                    "selector_fallbacks": ["input[name='email']"],
                    "value": "FILLED",
                    "timeout_ms": 1500,
                }
            ],
        )
        assert result["status"] == "success", result["errors"]

    # ── Injection ────────────────────────────────────────────────────────

    HOSTILE_PAYLOADS = [
        "a'], #decoy, [name='b",
        'a"b',
        "a\\b",
        "a\nb",
        "\n5",
        "], *",
        "x, body",
        "a\tb",
        "é中 z",
    ]

    @pytest.mark.parametrize("payload", HOSTILE_PAYLOADS)
    def test_template_data_cannot_retarget_an_attribute_locator(
        self, locator_pages: dict, payload: str
    ):
        """The page has no input whose name could equal the payload, so the only
        acceptable outcomes are "matched nothing" or "refused" — never a match on
        some other element."""
        result = self._run(
            locator_pages["before"],
            [
                {
                    "action": "fill",
                    "selector": "input[name='{{field}}']",
                    "value": "FILLED",
                    "timeout_ms": 1500,
                }
            ],
            data={"field": payload},
        )
        assert result["status"] == "failed"
        assert result["results"][0]["error_code"] == "ELEMENT_NOT_FOUND"

    def test_template_data_matching_a_real_value_still_lands_on_it(self, locator_pages: dict):
        """Fail-closed is not enough: a legitimate value must still work."""
        result = self._run(
            locator_pages["before"],
            [
                {
                    "action": "fill",
                    "selector": "input[name='{{field}}']",
                    "value": "FILLED",
                    "timeout_ms": 2000,
                }
            ],
            data={"field": "email"},
        )
        assert result["status"] == "success", result["errors"]

    def test_hostile_data_does_not_reach_the_browser_as_grammar(self, locator_pages: dict):
        """A payload shaped like a selector is treated as an opaque value."""
        result = self._run(
            locator_pages["before"],
            [
                {
                    "action": "click",
                    "locator": {"strategy": "testid", "value": "{{probe}}"},
                    "timeout_ms": 1200,
                }
            ],
            data={"probe": '"] , *['},
        )
        # No element has that test id; crucially it neither errored as a bad
        # selector nor clicked something else.
        assert result["results"][0]["error_code"] == "ELEMENT_NOT_FOUND"

    def test_nul_in_template_data_is_refused(self, locator_pages: dict):
        result = self._run(
            locator_pages["before"],
            [
                {
                    "action": "fill",
                    "selector": "input[name='{{field}}']",
                    "value": "FILLED",
                    "timeout_ms": 1500,
                }
            ],
            data={"field": "a\x00b"},
        )
        assert result["results"][0]["error_code"] == "TEMPLATE_ERROR"

    def test_css_grammar_position_is_refused_before_execution(self, locator_pages: dict):
        result = self._run(
            locator_pages["before"],
            [{"action": "click", "selector": "form#{{x}}-form > button"}],
            data={"x": "a"},
        )
        assert result["status"] == "failed"
        assert result["results"][0]["error_code"] == "TEMPLATE_ERROR"

    def test_xpath_template_is_refused(self, locator_pages: dict):
        result = self._run(
            locator_pages["before"],
            [{"action": "click", "selector": "//input[@name='{{x}}']"}],
            data={"x": "email"},
        )
        assert result["results"][0]["error_code"] == "TEMPLATE_ERROR"

    def test_wait_function_template_is_refused(self, locator_pages: dict):
        """The JavaScript route: refused before any page script runs."""
        result = self._run(
            locator_pages["before"],
            [
                {
                    "action": "wait",
                    "type": "function",
                    "value": "() => document.title === '{{x}}'",
                }
            ],
            data={"x": "a' || (window.__pwned = 1) || 'b"},
        )
        assert result["results"][0]["error_code"] == "TEMPLATE_ERROR"

    def test_matches_regex_template_is_refused(self, locator_pages: dict):
        """The ReDoS route: a templated pattern may never become a regex."""
        result = self._run(
            locator_pages["before"],
            [
                {
                    "action": "if",
                    "condition": {
                        "selector": "#a-form",
                        "operator": "matches_regex",
                        "expected_value": "{{pat}}",
                    },
                    "then": [{"action": "click", "selector": "#a-submit"}],
                }
            ],
            data={"pat": "(a+)+$"},
        )
        assert result["results"][0]["error_code"] == "TEMPLATE_ERROR"

    def test_extract_schema_uses_the_safe_path(self, locator_pages: dict):
        """Extract selectors bypassed the old render path entirely."""
        result = self._run(
            locator_pages["before"],
            [
                {
                    "action": "fill",
                    "selector": "input[name='{{field}}']",
                    "value": "FILLED",
                    "timeout_ms": 2000,
                }
            ],
            data={"field": "email"},
            extract_schema={
                "fields": [
                    {
                        "name": "value",
                        "selector": "input[name='{{field}}']",
                        "attribute": "value",
                        "redact": False,
                    }
                ]
            },
        )
        assert result["status"] == "success", result["errors"]
        assert result["extracted"]["value"] == "FILLED"

    # ── Legacy compatibility ─────────────────────────────────────────────

    def test_legacy_selector_still_works(self, locator_pages: dict):
        result = self._run(
            locator_pages["before"],
            [{"action": "fill", "selector": "#a-email", "value": "x", "timeout_ms": 2000}],
        )
        assert result["status"] == "success", result["errors"]

    def test_invalid_selector_syntax_still_reports_invalid_selector(self, locator_pages: dict):
        result = self._run(
            locator_pages["before"],
            [{"action": "click", "selector": ">>>", "timeout_ms": 1000}],
        )
        assert result["results"][0]["error_code"] == "INVALID_SELECTOR"

    def test_condition_selector_still_works(self, locator_pages: dict):
        result = self._run(
            locator_pages["before"],
            [
                {
                    "action": "if",
                    "condition": {"selector": "#a-form", "state": "exist"},
                    "then": [{"action": "fill", "selector": "#a-email", "value": "x"}],
                }
            ],
        )
        assert result["status"] == "success", result["errors"]
