"""Tests for template variable rendering."""

from web_auto_form.templates import render, render_dict


class TestRender:
    def test_simple_replacement(self):
        assert render("Hello {{name}}", {"name": "World"}) == "Hello World"

    def test_nested_dot_notation(self):
        data = {"user": {"name": "Alice", "email": "a@b.com"}}
        assert render("{{user.name}} <{{user.email}}>", data) == "Alice <a@b.com>"

    def test_missing_key_returns_empty(self):
        assert render("{{missing}}", {}) == ""

    def test_no_placeholders(self):
        assert render("no placeholders", {"x": 1}) == "no placeholders"

    def test_multiple_placeholders(self):
        data = {"a": "1", "b": "2"}
        assert render("{{a}}-{{b}}", data) == "1-2"


class TestRenderDict:
    def test_renders_nested_dict(self):
        data = {"name": "Bob"}
        obj = {"selector": "#{{name}}", "value": "hi {{name}}"}
        result = render_dict(obj, data)
        assert result == {"selector": "#Bob", "value": "hi Bob"}

    def test_renders_list(self):
        data = {"x": "val"}
        result = render_dict(["{{x}}", "static"], data)
        assert result == ["val", "static"]

    def test_non_string_passthrough(self):
        assert render_dict(42, {}) == 42
        assert render_dict(None, {}) is None
