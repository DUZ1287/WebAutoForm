"""Phase 1: execution reliability — containment, retry ownership, failure policy.

These tests drive the real :class:`~web_auto_form.runner.Runner` against a fake
Playwright page, so they exercise the actual execution path (exception boundary,
retry loop, failure policy, outcome propagation) rather than mocks of it.
"""

from __future__ import annotations

from typing import Any, Optional

import pytest
from playwright.sync_api import Error as PwError
from playwright.sync_api import TimeoutError as PwTimeout

import web_auto_form.runner as runner_mod
from web_auto_form import run

# ── Fake Playwright surface ─────────────────────────────────────────────────


class FakeLocator:
    def __init__(self, page: "FakePage", selector: str) -> None:
        self._page = page
        self._selector = selector

    @property
    def first(self) -> "FakeLocator":
        return self

    def _record(self, method: str) -> None:
        self._page.calls.append((method, self._selector))

    def _maybe_raise(self) -> None:
        exc = self._page.errors.get(self._selector)
        if exc is not None:
            raise exc

    # -- lookup -----------------------------------------------------------
    def wait_for(self, state: str = "attached", timeout: Optional[int] = None) -> None:
        self._record("wait_for")
        if self._selector in self._page.missing:
            raise PwTimeout(
                f"Timeout {timeout}ms exceeded.\nCall log:\n"
                f'  - waiting for locator("{self._selector}")'
            )

    def count(self) -> int:
        return 0 if self._selector in self._page.missing else 1

    def is_visible(self) -> bool:
        return self._selector not in self._page.unvisible

    def is_checked(self) -> bool:
        return self._selector not in self._page.unchecked

    # -- actions ----------------------------------------------------------
    def click(self, timeout: Optional[int] = None) -> None:
        self._record("click")
        self._maybe_raise()

    def fill(self, value: str, timeout: Optional[int] = None) -> None:
        self._record("fill")
        self._maybe_raise()

    def check(self, timeout: Optional[int] = None) -> None:
        self._record("check")
        self._maybe_raise()

    def uncheck(self, timeout: Optional[int] = None) -> None:
        self._record("uncheck")
        self._maybe_raise()

    def select_option(self, label: Optional[str] = None, timeout: Optional[int] = None) -> None:
        self._record("select_option")
        self._maybe_raise()

    def text_content(self) -> str:
        self._record("text_content")
        return "text"

    def input_value(self) -> str:
        return "value"

    def inner_html(self) -> str:
        return "<span/>"

    def get_attribute(self, name: str) -> str:
        return "attr"


class FakePage:
    """Just enough of Playwright's Page for the Runner to run against."""

    def __init__(
        self,
        missing: tuple[str, ...] = (),
        errors: Optional[dict[str, BaseException]] = None,
        unchecked: tuple[str, ...] = (),
    ) -> None:
        self.missing = set(missing)
        self.errors = dict(errors or {})
        self.unchecked = set(unchecked)
        self.unvisible: set[str] = set()
        self.calls: list[tuple[str, str]] = []
        self.goto_url: Optional[str] = None

    def goto(self, url: str, **kwargs: Any) -> None:
        self.goto_url = url

    def locator(self, selector: str) -> FakeLocator:
        return FakeLocator(self, selector)

    def evaluate(self, script: str) -> list[dict[str, str]]:
        self.calls.append(("evaluate", ""))
        return [{"tag": "input", "type": "email", "name": "email", "id": "email"}]

    def wait_for_load_state(self, *args: Any, **kwargs: Any) -> None:
        return None

    def wait_for_function(self, expression: str, **kwargs: Any) -> None:
        return None

    def count(self, method: str, selector: str) -> int:
        """How many times *method* was invoked on *selector*."""
        return sum(1 for m, s in self.calls if m == method and s == selector)


class FakeBrowserManager:
    def __init__(self, page: FakePage) -> None:
        self._page = page

    def launch(self) -> FakePage:
        return self._page

    @property
    def page(self) -> FakePage:
        return self._page

    def screenshot(self, full_page: bool = False) -> str:
        return "ZmFrZS1wbmc="

    def save_debug(self, path: str, step_index: int) -> None:
        return None

    def close(self) -> None:
        return None


@pytest.fixture
def run_with(monkeypatch: pytest.MonkeyPatch):
    """Execute a config against a fake browser page."""

    def _run(page: FakePage, steps: list[dict], **options: Any) -> dict:
        monkeypatch.setattr(
            runner_mod, "BrowserManager", lambda options_cfg: FakeBrowserManager(page)
        )
        opts: dict[str, Any] = {"headless": True, "step_delay_ms": 100}
        opts.update(options)
        return run(
            {
                "url": "https://example.com/form",
                "consent_statement": "Phase 1 reliability test.",
                "steps": steps,
                "options": opts,
            }
        )

    return _run


NETWORK_FAILURE = PwError("net::ERR_CONNECTION_REFUSED")
INVALID_SELECTOR_FAILURE = PwError('Unexpected token "!" while parsing css selector "#!"')


# ── 1. Exception containment ────────────────────────────────────────────────


class TestExceptionContainment:
    def test_playwright_exception_does_not_escape_run(self, run_with):
        page = FakePage(
            errors={
                "#go": PwTimeout(
                    'Timeout 5000ms exceeded.\nCall log:\n  - waiting for locator("#go")'
                )
            }
        )
        result = run_with(page, [{"action": "click", "selector": "#go"}])

        assert result["status"] == "failed"
        assert result["results"][0]["status"] == "failed"
        assert result["results"][0]["error_code"] == "ELEMENT_NOT_FOUND"
        assert result["errors"]

    def test_exception_after_success_still_reports_earlier_steps(self, run_with):
        page = FakePage(errors={"#bad": NETWORK_FAILURE})
        result = run_with(
            page,
            [
                {"action": "click", "selector": "#one"},
                {"action": "click", "selector": "#bad"},
            ],
        )
        assert result["steps_executed"] == 2
        assert result["results"][0]["status"] == "ok"
        assert result["results"][1]["error_code"] == "NETWORK_ERROR"

    def test_initial_navigation_failure_is_contained(self, run_with, monkeypatch):
        page = FakePage()

        def boom(url: str, **kwargs: Any) -> None:
            raise PwError("net::ERR_NAME_NOT_RESOLVED")

        monkeypatch.setattr(page, "goto", boom)
        result = run_with(page, [{"action": "click", "selector": "#one"}])

        assert result["status"] == "failed"
        assert result["aborted"] is True
        assert result["errors"][0]["code"] == "NETWORK_ERROR"

    def test_unexpected_exception_becomes_internal_error(self, run_with):
        page = FakePage(errors={"#go": ValueError("boom")})
        result = run_with(page, [{"action": "click", "selector": "#go"}])

        step = result["results"][0]
        assert step["error_code"] == "INTERNAL_ERROR"
        assert step["retryable"] is False
        assert "ValueError" in step["error"]

    def test_debug_mode_keeps_traceback(self, run_with):
        page = FakePage(errors={"#go": ValueError("boom")})
        result = run_with(page, [{"action": "click", "selector": "#go"}], debug=True)

        assert "traceback" in result["results"][0]["diagnostics"]

    def test_launch_failure_is_contained_and_cleans_up(self, monkeypatch):
        """A failed launch must not leak the Playwright sync driver."""
        closed: list[bool] = []

        class BoomBrowser:
            def launch(self):
                raise PwError("BrowserType.launch: Executable doesn't exist")

            def close(self) -> None:
                closed.append(True)

        monkeypatch.setattr(runner_mod, "BrowserManager", lambda options_cfg: BoomBrowser())
        result = run(
            {
                "url": "https://example.com",
                "consent_statement": "Phase 1 reliability test.",
                "steps": [{"action": "click", "selector": "#one"}],
            }
        )

        assert result["status"] == "failed"
        assert result["aborted"] is True
        assert result["steps_executed"] == 0
        assert closed == [True], "browser manager must be closed even if launch failed"


# ── 2. Retry ownership and count ────────────────────────────────────────────


class TestRetrySemantics:
    def test_max_retries_two_means_three_attempts(self, run_with):
        page = FakePage(errors={"#go": NETWORK_FAILURE})
        result = run_with(page, [{"action": "click", "selector": "#go", "max_retries": 2}])

        assert page.count("click", "#go") == 3
        assert result["results"][0]["retries"] == 2

    def test_no_retries_means_one_attempt(self, run_with):
        page = FakePage(errors={"#go": NETWORK_FAILURE})
        result = run_with(page, [{"action": "click", "selector": "#go", "max_retries": 1}])

        assert page.count("click", "#go") == 2  # 1 initial + 1 retry
        assert result["results"][0]["retries"] == 1

    def test_non_retryable_error_is_not_repeated(self, run_with):
        page = FakePage(errors={"#go": INVALID_SELECTOR_FAILURE})
        result = run_with(page, [{"action": "click", "selector": "#go", "max_retries": 5}])

        assert page.count("click", "#go") == 1
        assert result["results"][0]["error_code"] == "INVALID_SELECTOR"
        assert result["results"][0]["retryable"] is False

    def test_retryable_but_not_in_retry_on_is_not_retried(self, run_with):
        # ELEMENT_NOT_VISIBLE is intrinsically retryable, but TIMEOUT-only policy
        # does not admit it.
        page = FakePage(errors={"#go": PwError("Element is not visible")})
        result = run_with(
            page,
            [{"action": "click", "selector": "#go", "max_retries": 3}],
            retry_on=["TIMEOUT"],
        )
        assert page.count("click", "#go") == 1
        assert result["results"][0]["error_code"] == "ELEMENT_NOT_VISIBLE"
        assert result["results"][0]["retryable"] is True

    def test_on_fail_retry_overrides_retry_on_gate(self, run_with):
        page = FakePage(errors={"#go": INVALID_SELECTOR_FAILURE})
        result = run_with(
            page,
            [
                {
                    "action": "click",
                    "selector": "#go",
                    "on_fail": "retry",
                    "max_retries": 2,
                }
            ],
            retry_on=["NETWORK_ERROR"],
        )
        assert page.count("click", "#go") == 3
        assert result["results"][0]["retries"] == 2


# ── 3. Failure policy: abort / continue / optional ──────────────────────────


class TestFailurePolicy:
    def test_abort_stops_remaining_steps(self, run_with):
        page = FakePage(errors={"#two": NETWORK_FAILURE})
        result = run_with(
            page,
            [
                {"action": "click", "selector": "#one"},
                {"action": "click", "selector": "#two", "max_retries": 1},
                {"action": "click", "selector": "#three"},
            ],
        )

        assert page.count("click", "#one") == 1
        assert page.count("click", "#three") == 0
        assert result["status"] == "failed"
        assert result["aborted"] is True
        assert result["steps_failed"] == 1

    def test_continue_runs_remaining_steps_and_reports_partial(self, run_with):
        page = FakePage(errors={"#two": NETWORK_FAILURE})
        result = run_with(
            page,
            [
                {"action": "click", "selector": "#one"},
                {"action": "click", "selector": "#two", "on_fail": "continue", "max_retries": 1},
                {"action": "click", "selector": "#three"},
            ],
        )

        assert page.count("click", "#three") == 1
        assert result["status"] == "partial"
        assert result["aborted"] is False
        assert result["steps_failed"] == 1
        assert result["results"][1]["status"] == "failed"

    def test_optional_failure_keeps_workflow_successful(self, run_with):
        page = FakePage(missing={"#optional"})
        result = run_with(
            page,
            [
                {
                    "action": "fill",
                    "selector": "#optional",
                    "value": "x",
                    "optional": True,
                    "timeout_ms": 200,
                },
                {"action": "click", "selector": "#next"},
            ],
        )

        assert result["status"] == "success"
        assert result["steps_skipped"] == 1
        assert result["steps_failed"] == 0
        assert result["results"][0]["status"] == "skipped"
        assert result["results"][0]["error_code"] == "ELEMENT_NOT_FOUND"
        assert page.count("click", "#next") == 1

    def test_optional_with_on_skip_abort_still_aborts(self, run_with):
        page = FakePage(missing={"#optional"})
        result = run_with(
            page,
            [
                {
                    "action": "fill",
                    "selector": "#optional",
                    "value": "x",
                    "optional": True,
                    "on_skip": "abort",
                    "timeout_ms": 200,
                },
                {"action": "click", "selector": "#next"},
            ],
        )

        assert result["status"] == "failed"
        assert result["aborted"] is True
        assert page.count("click", "#next") == 0

    def test_retry_exhaustion_then_aborts(self, run_with):
        page = FakePage(errors={"#go": NETWORK_FAILURE})
        result = run_with(
            page,
            [
                {"action": "click", "selector": "#go", "max_retries": 2},
                {"action": "click", "selector": "#after"},
            ],
        )

        assert page.count("click", "#go") == 3
        assert page.count("click", "#after") == 0
        assert result["status"] == "failed"


# ── 4. Nested abort propagation ─────────────────────────────────────────────


class TestNestedAbortPropagation:
    def test_abort_inside_if_propagates_to_top_level(self, run_with):
        page = FakePage(errors={"#bad": NETWORK_FAILURE})
        result = run_with(
            page,
            [
                {"action": "click", "selector": "#before"},
                {
                    "action": "if",
                    "condition": {"selector": "#flag", "state": "checked"},
                    "then": [
                        {"action": "fill", "selector": "#a", "value": "x"},
                        {"action": "click", "selector": "#bad", "max_retries": 1},
                        {"action": "fill", "selector": "#never", "value": "x"},
                    ],
                },
                {"action": "click", "selector": "#after"},
            ],
        )

        assert page.count("fill", "#a") == 1
        assert page.count("fill", "#never") == 0, "rest of then-branch must be skipped"
        assert page.count("click", "#after") == 0, "top-level steps must be skipped"
        assert result["status"] == "failed"
        assert result["aborted"] is True

    def test_else_branch_used_when_condition_is_false(self, run_with):
        page = FakePage(unchecked={"#flag"})
        result = run_with(
            page,
            [
                {
                    "action": "if",
                    "condition": {"selector": "#flag", "state": "checked"},
                    "then": [{"action": "fill", "selector": "#yes", "value": "x"}],
                    "else": [{"action": "fill", "selector": "#no", "value": "x"}],
                },
            ],
        )

        assert page.count("fill", "#yes") == 0
        assert page.count("fill", "#no") == 1
        assert result["status"] == "success"


# ── 5. Assert semantics ─────────────────────────────────────────────────────


class TestAssertSemantics:
    def test_assert_retry_attempts_follow_max_retries(self, run_with):
        page = FakePage(missing={"#never"})
        result = run_with(
            page,
            [
                {
                    "action": "assert",
                    "selector": "#never",
                    "state": "visible",
                    "on_fail": "retry",
                    "max_retries": 2,
                    "timeout_ms": 200,
                }
            ],
        )

        assert page.count("wait_for", "#never") == 3, "assert must not double-retry"
        assert result["results"][0]["retries"] == 2
        assert result["results"][0]["error_code"] == "ASSERTION_FAILED"

    def test_assert_abort_stops_workflow(self, run_with):
        page = FakePage(missing={"#never"})
        result = run_with(
            page,
            [
                {"action": "assert", "selector": "#never", "state": "visible", "timeout_ms": 200},
                {"action": "click", "selector": "#after"},
            ],
        )

        assert page.count("wait_for", "#never") == 1
        assert page.count("click", "#after") == 0
        assert result["status"] == "failed"

    def test_assert_continue_reports_partial(self, run_with):
        page = FakePage(missing={"#never"})
        result = run_with(
            page,
            [
                {
                    "action": "assert",
                    "selector": "#never",
                    "state": "visible",
                    "on_fail": "continue",
                    "timeout_ms": 200,
                },
                {"action": "click", "selector": "#after"},
            ],
        )

        assert page.count("wait_for", "#never") == 1
        assert page.count("click", "#after") == 1
        assert result["status"] == "partial"

    def test_assert_not_exist_fails_when_element_persists(self, run_with):
        # A timeout waiting for "detached" means the element never went away.
        page = FakePage(missing={"#err"})
        result = run_with(
            page,
            [
                {
                    "action": "assert",
                    "selector": "#err",
                    "state": "not_exist",
                    "timeout_ms": 200,
                }
            ],
        )

        assert result["results"][0]["status"] == "failed"
        assert result["results"][0]["error_code"] == "ASSERTION_FAILED"


# ── 6. Diagnostics ──────────────────────────────────────────────────────────


class TestDiagnostics:
    def test_diagnostics_survive_exception_containment(self, run_with):
        page = FakePage(errors={"#go": PwTimeout("Timeout 5000ms exceeded.")})
        result = run_with(page, [{"action": "click", "selector": "#go"}])

        diagnostics = result["results"][0]["diagnostics"]
        assert diagnostics["screenshot"] == "ZmFrZS1wbmc="
        assert diagnostics["form_elements"][0]["name"] == "email"

    def test_diagnostics_captured_once_for_final_failed_attempt(self, run_with):
        page = FakePage(errors={"#go": NETWORK_FAILURE})
        run_with(page, [{"action": "click", "selector": "#go", "max_retries": 2}])

        screenshots = [c for c in page.calls if c[0] == "evaluate"]
        assert len(screenshots) == 1, "only the final failed attempt should be captured"

    def test_diagnostics_can_be_disabled(self, run_with):
        page = FakePage(errors={"#go": NETWORK_FAILURE})
        result = run_with(page, [{"action": "click", "selector": "#go"}], diagnose_on_failure=False)
        assert "diagnostics" not in result["results"][0]


# ── 7. Workflow status contract ─────────────────────────────────────────────


class TestWorkflowStatus:
    def test_all_success(self, run_with):
        page = FakePage()
        result = run_with(page, [{"action": "click", "selector": "#one"}])

        assert result["status"] == "success"
        assert result["aborted"] is False
        assert result["errors"] == []

    def test_skipped_optional_only_is_still_success(self, run_with):
        page = FakePage(missing={"#opt"})
        result = run_with(
            page,
            [
                {
                    "action": "click",
                    "selector": "#opt",
                    "optional": True,
                    "timeout_ms": 200,
                }
            ],
        )
        assert result["status"] == "success"
        assert result["steps_skipped"] == 1
        assert result["steps_executed"] == 0

    def test_failures_are_reported_in_errors_list(self, run_with):
        page = FakePage(errors={"#bad": NETWORK_FAILURE})
        result = run_with(page, [{"action": "click", "selector": "#bad", "on_fail": "continue"}])
        assert result["errors"]
        assert result["errors"][0]["code"] == "NETWORK_ERROR"
        assert result["errors"][0]["step"] == 0
