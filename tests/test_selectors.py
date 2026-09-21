"""Tests for selector detection, resolution, and the fallback chain."""

import pytest
from playwright.sync_api import Error as PwError
from playwright.sync_api import TimeoutError as PwTimeout

from web_auto_form.selectors import detect_selector_type, find_element, resolve_selector


class TestDetectSelectorType:
    def test_xpath(self):
        assert detect_selector_type("//div[@id='x']") == "xpath"

    def test_id(self):
        assert detect_selector_type("#my-id") == "id"

    def test_name(self):
        assert detect_selector_type("[name='email']") == "name"

    def test_placeholder(self):
        assert detect_selector_type("[placeholder='Enter email']") == "placeholder"

    def test_data_testid(self):
        assert detect_selector_type("[data-testid='submit']") == "data-testid"

    def test_css_default(self):
        assert detect_selector_type("div.form > input") == "css"

    def test_id_with_space_falls_back_to_css(self):
        assert detect_selector_type("#id .child") == "css"


class TestResolveSelector:
    def test_xpath_passthrough(self):
        assert resolve_selector("//div", "xpath") == "//div"

    def test_id_conversion(self):
        assert resolve_selector("my-id", "id") == "#my-id"

    def test_id_with_hash(self):
        assert resolve_selector("#my-id", "id") == "#my-id"

    def test_name_conversion(self):
        assert resolve_selector("[name='email']", "name") == "[name='email']"

    def test_css_passthrough(self):
        assert resolve_selector("div > input", "css") == "div > input"

    def test_auto_detect_integration(self):
        assert resolve_selector("//span") == "//span"
        assert resolve_selector("#foo") == "#foo"


class _FakeLocator:
    def __init__(self, page: "_FakePage", selector: str) -> None:
        self._page = page
        self._selector = selector

    @property
    def first(self) -> "_FakeLocator":
        return self

    def wait_for(self, state: str = "attached", timeout: int | None = None) -> None:
        behaviour = self._page.behaviour.get(self._selector)
        if behaviour is not None:
            raise behaviour
        if self._selector not in self._page.present:
            raise PwTimeout("Timeout 3000ms exceeded.")

    def count(self) -> int:
        return 1 if self._selector in self._page.present else 0


class _FakePage:
    def __init__(self, present=(), behaviour=None) -> None:
        self.present = set(present)
        self.behaviour = dict(behaviour or {})

    def locator(self, selector: str) -> _FakeLocator:
        return _FakeLocator(self, selector)


class TestFindElement:
    def test_returns_none_when_nothing_matches(self):
        page = _FakePage(present={"#other"})
        assert find_element(page, "#missing") is None

    def test_returns_first_match(self):
        page = _FakePage(present={"#hit"})
        assert find_element(page, "#hit").count() == 1

    def test_falls_back_to_backup_selector(self):
        page = _FakePage(present={"#backup"})
        assert find_element(page, "#primary", ["#backup"]) is not None

    def test_reraises_structural_error_when_nothing_matches(self):
        """An invalid selector must not be reported as 'element not found'."""
        page = _FakePage(behaviour={"#bad": PwError('Unexpected token "."')})
        with pytest.raises(PwError):
            find_element(page, "#bad")

    def test_structural_error_does_not_fall_through_to_fallback(self):
        """A malformed candidate aborts the chain — it is a config defect, and
        silently using a backup would hide it and make behaviour depend on which
        candidate happened to be broken."""
        page = _FakePage(present={"#backup"}, behaviour={"#bad": PwError("Unexpected token")})
        with pytest.raises(PwError):
            find_element(page, "#bad", ["#backup"])

    def test_absent_primary_still_falls_through_to_fallback(self):
        """A candidate that merely does not match must still advance."""
        page = _FakePage(present={"#backup"})
        assert find_element(page, "#absent", ["#backup"]) is not None
