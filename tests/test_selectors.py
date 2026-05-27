"""Tests for selector detection and resolution."""

from web_auto_form.selectors import detect_selector_type, resolve_selector


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
