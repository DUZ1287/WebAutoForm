"""Tests for the structured error model: codes, classification, retryability."""

from playwright.sync_api import Error as PwError
from playwright.sync_api import TimeoutError as PwTimeout

from web_auto_form.errors import (
    RETRYABLE_CODES,
    ErrorCode,
    ErrorInfo,
    classify_exception,
)


class TestErrorInfo:
    def test_retryable_is_derived_from_code(self):
        assert ErrorInfo(ErrorCode.TIMEOUT, "x").retryable is True
        assert ErrorInfo(ErrorCode.INVALID_SELECTOR, "x").retryable is False

    def test_element_not_found_is_not_intrinsically_retryable(self):
        # find_element already spent the full timeout on the fallback chain.
        assert ErrorCode.ELEMENT_NOT_FOUND not in RETRYABLE_CODES

    def test_all_codes_are_classified(self):
        for code in ErrorCode:
            assert isinstance(code in RETRYABLE_CODES, bool)


class TestClassifyPlaywrightTimeout:
    def test_navigate_timeout(self):
        exc = PwTimeout("Timeout 30000ms exceeded.\nCall log:\n  - navigating to ...")
        assert classify_exception(exc, "navigate").code is ErrorCode.NAVIGATION_FAILED

    def test_load_state_timeout(self):
        exc = PwTimeout("Timeout 5000ms exceeded.\nCall log:\n  - waiting for load state")
        assert classify_exception(exc, "wait").code is ErrorCode.NAVIGATION_FAILED

    def test_locator_never_appeared_is_not_found(self):
        exc = PwTimeout('Timeout 5000ms exceeded.\nCall log:\n  - waiting for locator("#missing")')
        assert classify_exception(exc, "click").code is ErrorCode.ELEMENT_NOT_FOUND

    def test_locator_resolved_but_hidden_is_not_visible(self):
        exc = PwTimeout(
            "Timeout 5000ms exceeded.\nCall log:\n"
            '  - waiting for locator("#x")\n'
            "  - locator resolved to <input .../>\n"
            "  - element is not visible"
        )
        assert classify_exception(exc, "click").code is ErrorCode.ELEMENT_NOT_VISIBLE

    def test_bare_timeout(self):
        assert classify_exception(PwTimeout("Timeout exceeded."), "wait").code is ErrorCode.TIMEOUT

    def test_covered_element_beats_locator_resolved(self):
        """A covered element resolves, so it must not fall into NOT_VISIBLE."""
        exc = PwTimeout(
            "Timeout 5000ms exceeded.\nCall log:\n"
            '  - waiting for locator("#btn")\n'
            '    - locator resolved to <button id="btn">B</button>\n'
            "    - attempting click action\n"
            "      - <div> intercepts pointer events\n"
            "  - retrying click action"
        )
        assert classify_exception(exc, "click").code is ErrorCode.ELEMENT_NOT_INTERACTABLE

    def test_disabled_element_beats_locator_resolved(self):
        exc = PwTimeout(
            "Timeout 5000ms exceeded.\nCall log:\n"
            '  - waiting for locator("#btn")\n'
            '    - locator resolved to <button id="btn" disabled>B</button>\n'
            "      - element is not enabled"
        )
        assert classify_exception(exc, "click").code is ErrorCode.ELEMENT_NOT_INTERACTABLE


class TestClassifyPlaywrightError:
    def test_invalid_selector(self):
        exc = PwError('Unexpected token "!" while parsing css selector "#!"')
        assert classify_exception(exc, "click").code is ErrorCode.INVALID_SELECTOR

    def test_network_error(self):
        exc = PwError("net::ERR_CONNECTION_REFUSED at https://example.com")
        assert classify_exception(exc, "navigate").code is ErrorCode.NETWORK_ERROR

    def test_network_error_matches_whole_err_family(self):
        # New net::ERR_* codes must not silently degrade to UNKNOWN.
        exc = PwError("Page.goto: net::ERR_UNSAFE_PORT at http://127.0.0.1:9/")
        assert classify_exception(exc, "run").code is ErrorCode.NETWORK_ERROR

    def test_err_aborted_is_navigation_not_network(self):
        exc = PwError("Page.goto: net::ERR_ABORTED at https://example.com")
        assert classify_exception(exc, "navigate").code is ErrorCode.NAVIGATION_FAILED

    def test_element_not_interactable(self):
        exc = PwError("Element is not stable")
        assert classify_exception(exc, "click").code is ErrorCode.ELEMENT_NOT_INTERACTABLE

    def test_intercepted_click(self):
        exc = PwError("<div> intercepts pointer events")
        assert classify_exception(exc, "click").code is ErrorCode.ELEMENT_NOT_INTERACTABLE

    def test_target_closed(self):
        exc = PwError("Target page, context or browser has been closed")
        assert classify_exception(exc, "click").code is ErrorCode.INTERNAL_ERROR

    def test_unclassified_playwright_error(self):
        assert classify_exception(PwError("something odd"), "click").code is ErrorCode.UNKNOWN

    def test_upload_action_absorbs_unclassified_errors(self):
        exc = PwError("File not found: /tmp/x.pdf")
        assert classify_exception(exc, "upload").code is ErrorCode.FILE_UPLOAD_FAILED


class TestClassifyNonPlaywright:
    def test_oserror_during_upload(self):
        assert classify_exception(FileNotFoundError("nope"), "upload").code is (
            ErrorCode.FILE_UPLOAD_FAILED
        )

    def test_programming_error_is_internal(self):
        assert classify_exception(ValueError("boom"), "fill").code is ErrorCode.INTERNAL_ERROR

    def test_message_is_single_line(self):
        exc = ValueError("first line\nsecond line\nthird line")
        info = classify_exception(exc, "fill")
        assert "\n" not in info.message
        assert "ValueError" in info.message

    def test_playwright_message_has_no_type_prefix(self):
        info = classify_exception(PwTimeout("Timeout 5000ms exceeded."), "click")
        assert not info.message.startswith("TimeoutError")
