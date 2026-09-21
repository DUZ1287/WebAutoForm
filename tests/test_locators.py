"""Locator normalization, template safety, and fallback semantics (no browser).

The security property under test is *not* "every character gets escaped". It is:

    untrusted data must not be able to change a locator's structure or make it
    target an unrelated element.

So the escaper is checked against a structural invariant (the produced CSS string
cannot be terminated early), and the policy is checked by proving that
unescapable positions are refused outright rather than "handled".
"""

from __future__ import annotations

import pytest

from web_auto_form.models import LocatorSpec, StepConfig
from web_auto_form.selectors import (
    build_locator_chain,
    css_string,
    normalize_selector,
    render_locator,
    resolve_locator,
)
from web_auto_form.templates import TemplateSecurityError

HOSTILE = [
    "a'], .decoy, [name='b",
    'a"b',
    "a\\b",
    "a\nb",
    "a\rb",
    "a\fb",
    "5\n5",
    "\nA",
    "trailing\\",
    "], *",
    "x, body",
    "a\tb",
    "",
    "é中 z",
    "'",
    '"',
    "\\",
]


def _assert_string_cannot_terminate_early(escaped: str) -> None:
    """The escaped value must be one balanced, unterminated CSS string."""
    assert escaped.startswith('"') and escaped.endswith('"'), escaped
    body = escaped[1:-1]
    index = 0
    while index < len(body):
        char = body[index]
        if char == "\\":
            index += 2  # the following character is escaped
            continue
        assert char != '"', f"unescaped quote breaks out: {escaped!r}"
        index += 1
    assert index == len(body), f"dangling escape at end: {escaped!r}"


class TestCssStringEscaper:
    @pytest.mark.parametrize("value", HOSTILE)
    def test_output_cannot_break_out_of_the_string(self, value: str):
        _assert_string_cannot_terminate_early(css_string(value))

    def test_backslash_is_doubled_before_quote(self):
        assert css_string('a\\"b') == '"a\\\\\\"b"'

    def test_newline_uses_hex_escape_with_terminating_space(self):
        # The trailing space is load-bearing: without it a following hex digit
        # from the data merges into the escape ("\n" + "5" -> U+00A5).
        assert css_string("\n5") == '"\\a 5"'

    def test_hex_terminator_does_not_leak_into_the_value(self):
        assert css_string("\nA") == '"\\a A"'

    def test_carriage_return_and_form_feed(self):
        assert css_string("\r") == '"\\d "'
        assert css_string("\f") == '"\\c "'

    def test_nul_is_refused_not_escaped(self):
        """U+0000 maps to U+FFFD in CSS, so it would match a *different* element."""
        with pytest.raises(TemplateSecurityError, match="NUL"):
            css_string("a\x00b")

    def test_plain_values_pass_through_unchanged(self):
        assert css_string("email") == '"email"'

    def test_single_quote_is_not_escaped_in_a_double_quoted_string(self):
        assert css_string("a'b") == '"a\'b"'


class TestNormalizeSelector:
    def test_untargeted_step_has_an_empty_chain(self):
        step = StepConfig(action="navigate", value="https://example.com")
        assert build_locator_chain(step) == []

    def test_placeholder_free_selector_is_used_verbatim(self):
        """Trusted configuration keeps the exact previous behaviour."""
        assert normalize_selector("#email") == LocatorSpec(strategy="css", value="#email")
        assert normalize_selector("div.form > input").value == "div.form > input"
        assert normalize_selector("//div[@id='x']") == LocatorSpec(
            strategy="xpath", value="//div[@id='x']"
        )

    def test_engine_prefixed_selectors_are_not_rewritten(self):
        spec = normalize_selector("text=Submit")
        assert spec.strategy == "css" and spec.value == "text=Submit"

    @pytest.mark.parametrize(
        "selector,strategy,attr",
        [
            ("[name='{{x}}']", "name", None),
            ('[name="{{x}}"]', "name", None),
            ("[name={{x}}]", "name", None),
            ("[data-testid='{{x}}']", "attr", "data-testid"),
            ("[placeholder='{{x}}']", "attr", "placeholder"),
        ],
    )
    def test_templated_attribute_selectors_normalize_safely(self, selector, strategy, attr):
        spec = normalize_selector(selector)
        assert spec.strategy == strategy
        if attr:
            assert spec.attr == attr
        assert spec.value == "{{x}}"

    @pytest.mark.parametrize(
        "selector,prefix,resolved",
        [
            # verbatim, so a trailing space stays a descendant combinator
            ("input[name='{{x}}']", "input", 'input[name="A"]'),
            ("#wrap [name='{{x}}']", "#wrap ", '#wrap [name="A"]'),
            ("div.form input[name='{{x}}']", "div.form input", 'div.form input[name="A"]'),
            ("form > input[name='{{x}}']", "form > input", 'form > input[name="A"]'),
        ],
    )
    def test_literal_prefix_is_preserved_verbatim(self, selector, prefix, resolved):
        """The prefix is grammar but provably placeholder-free, so it may stay —
        and the combinator spacing the author wrote must survive."""
        spec = normalize_selector(selector)
        assert spec.strategy == "attr" and spec.prefix == prefix

        page = _StubPage()
        resolve_locator(page, spec.model_copy(update={"value": "A"}))
        assert page.calls == [("locator", resolved)]

    @pytest.mark.parametrize(
        "selector",
        [
            "input[name='{{x}}'] [type='text']",
            "input[name='{{x}}'][type='text']",
            "div[class='{{x}}'] span",
            "input[title=\"a\"][name='{{x}}']",
        ],
    )
    def test_a_second_grammar_position_is_refused(self, selector):
        """A suffix or second attribute test would need grammar data can reach."""
        with pytest.raises(TemplateSecurityError):
            normalize_selector(selector)

    def test_partial_placeholder_is_kept_as_a_whole_value(self):
        """`prefix-{{x}}` renders then escapes as one value — safe and better
        than escaping a fragment."""
        spec = normalize_selector("[name='user-{{x}}']")
        assert spec.strategy == "name" and spec.value == "user-{{x}}"

    def test_id_placeholder_becomes_an_exact_attribute_match(self):
        spec = normalize_selector("#{{x}}")
        assert spec.strategy == "id" and spec.value == "{{x}}"

    def test_attribute_operator_is_preserved(self):
        spec = normalize_selector("[href^='{{url}}']")
        assert spec.strategy == "attr" and spec.attr == "href" and spec.op == "^="

    @pytest.mark.parametrize(
        "selector",
        [
            "div.{{cls}} > input",
            "//div[@id='{{x}}']",
            "//span[text()='{{x}}']",
            ".a-{{x}}",
            "{{selector}}",
            "[{{attr}}='literal']",
            "[name='{{x}}'] [type='text']",
        ],
    )
    def test_unescapable_positions_are_refused(self, selector):
        with pytest.raises(TemplateSecurityError):
            normalize_selector(selector)

    def test_xpath_is_refused_even_with_an_explicit_type(self):
        with pytest.raises(TemplateSecurityError, match="XPath"):
            normalize_selector("[name='{{x}}']", "xpath")


class TestRenderLocator:
    def test_semantic_value_is_substituted_as_an_argument(self):
        spec = render_locator(LocatorSpec(strategy="label", value="{{label}}"), {"label": "Email"})
        assert spec.value == "Email"

    def test_role_and_name_are_both_substituted(self):
        spec = render_locator(
            LocatorSpec(strategy="role", role="{{r}}", name="{{n}}"),
            {"r": "button", "n": "Submit"},
        )
        assert (spec.role, spec.name) == ("button", "Submit")

    def test_css_locator_with_a_placeholder_is_refused_at_render_time(self):
        spec = LocatorSpec(strategy="css", value="div.{{x}}")
        with pytest.raises(TemplateSecurityError):
            render_locator(spec, {"x": "y"})

    def test_nul_in_a_rendered_value_is_refused(self):
        spec = LocatorSpec(strategy="name", value="{{x}}")
        with pytest.raises(TemplateSecurityError, match="NUL"):
            render_locator(spec, {"x": "a\x00b"})

    def test_missing_variable_renders_empty_and_is_still_valid(self):
        spec = render_locator(LocatorSpec(strategy="label", value="{{missing}}"), {})
        assert spec.value == ""


class TestLocatorSpecValidation:
    def test_role_requires_a_role(self):
        with pytest.raises(ValueError):
            LocatorSpec(strategy="role", value="button")

    def test_attr_requires_attr_and_value(self):
        with pytest.raises(ValueError):
            LocatorSpec(strategy="attr", attr="name")

    def test_value_strategies_require_a_value(self):
        with pytest.raises(ValueError):
            LocatorSpec(strategy="label")


class TestStepConfigLocatorRules:
    def _step(self, **kwargs):
        return StepConfig(action="click", **kwargs)

    def test_selector_and_locator_cannot_both_be_given(self):
        with pytest.raises(ValueError, match="not both"):
            self._step(selector="#a", locator={"strategy": "label", "value": "A"})

    def test_fallback_forms_cannot_be_mixed(self):
        with pytest.raises(ValueError, match="not both"):
            self._step(
                selector="#a",
                selector_fallbacks=["#b"],
                locator_fallbacks=[{"strategy": "label", "value": "A"}],
            )

    def test_locator_alone_is_valid(self):
        step = self._step(locator={"strategy": "label", "value": "Email"})
        assert build_locator_chain(step)[0].strategy == "label"

    def test_locator_fallbacks_require_a_locator(self):
        with pytest.raises(ValueError, match="requires 'locator'"):
            self._step(selector="#a", locator_fallbacks=[{"strategy": "label", "value": "A"}])

    def test_target_is_required(self):
        with pytest.raises(ValueError, match="requires a selector or locator"):
            self._step()

    def test_new_locator_dsl_builds_a_chain(self):
        step = self._step(
            locator={"strategy": "role", "role": "button", "name": "Submit"},
            locator_fallbacks=[{"strategy": "testid", "value": "submit"}],
        )
        chain = build_locator_chain(step)
        assert [spec.strategy for spec in chain] == ["role", "testid"]


class _StubPage:
    """Records what selector each strategy produced."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def locator(self, selector: str):
        self.calls.append(("locator", selector))
        return _StubLocator(self, selector)

    def get_by_label(self, value, exact=False):
        self.calls.append(("label", f"{value}|exact={exact}"))
        return _StubLocator(self, value)

    def get_by_role(self, role, name=None, exact=False):
        self.calls.append(("role", f"{role}|{name}|exact={exact}"))
        return _StubLocator(self, role)

    def get_by_text(self, value, exact=False):
        self.calls.append(("text", f"{value}|exact={exact}"))
        return _StubLocator(self, value)

    def get_by_placeholder(self, value, exact=False):
        self.calls.append(("placeholder", f"{value}|exact={exact}"))
        return _StubLocator(self, value)

    def get_by_test_id(self, value):
        self.calls.append(("testid", value))
        return _StubLocator(self, value)


class _StubLocator:
    def __init__(self, page: _StubPage, key: str) -> None:
        self._page = page
        self._key = key

    @property
    def first(self):
        return self


class TestResolveLocator:
    def test_id_uses_an_attribute_attribute_test_not_a_bare_identifier(self):
        page = _StubPage()
        resolve_locator(page, LocatorSpec(strategy="id", value='a b"c'))
        assert page.calls == [("locator", '[id="a b\\"c"]')]

    def test_attr_keeps_the_operator(self):
        page = _StubPage()
        resolve_locator(page, LocatorSpec(strategy="attr", attr="href", op="^=", value="x"))
        assert page.calls == [("locator", '[href^="x"]')]

    def test_attr_prefix_is_concatenated_not_spaced(self):
        """`input [name=...]` would be a descendant selector — a different,
        non-matching selector than the compound one the author wrote."""
        page = _StubPage()
        resolve_locator(
            page,
            LocatorSpec(strategy="attr", attr="name", value="email", prefix="input"),
        )
        assert page.calls == [("locator", 'input[name="email"]')]

    def test_semantic_strategies_use_native_playwright_matchers(self):
        page = _StubPage()
        resolve_locator(page, LocatorSpec(strategy="label", value="Email", exact=True))
        resolve_locator(page, LocatorSpec(strategy="testid", value="user"))
        assert page.calls == [("label", "Email|exact=True"), ("testid", "user")]

    def test_semantic_strategies_are_not_assembled_into_css(self):
        page = _StubPage()
        resolve_locator(
            page, LocatorSpec(strategy="role", role="button", name="Submit", exact=True)
        )
        assert page.calls[0][0] == "role"

    def test_css_passes_through_unchanged(self):
        page = _StubPage()
        resolve_locator(page, LocatorSpec(strategy="css", value="div > input"))
        assert page.calls == [("locator", "div > input")]

    def test_xpath_gets_an_explicit_engine_prefix(self):
        page = _StubPage()
        resolve_locator(page, LocatorSpec(strategy="xpath", value="div"))
        assert page.calls == [("locator", "xpath=div")]
