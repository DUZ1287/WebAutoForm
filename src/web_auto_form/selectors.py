"""Locator normalization, template safety, and resolution.

Three deliberately separate stages::

    normalize_selector()   legacy string  ─┐
                                           ├─► LocatorSpec
    (config `locator`)     LocatorSpec    ─┘
    render_locator()       LocatorSpec + data ─► LocatorSpec   (escape or refuse)
    resolve_locator()      LocatorSpec ─► Playwright Locator

Why the split
-------------
Which escaping rule applies depends on the *strategy*, and the strategy has to
come from configuration. Deriving it by sniffing a rendered string — as the old
``detect_selector_type`` did — lets untrusted data choose its own defence.

The trust boundary is the placeholder:

* A selector with **no** ``{{...}}`` is authored configuration. It is trusted and
  is used verbatim, exactly as before.
* A selector **with** one is carrying untrusted data. That data is confined to a
  value slot that can be escaped correctly for its grammar (see
  :func:`css_string`), and never reaches a CSS/XPath grammar position.
"""

from __future__ import annotations

import logging
import re
from typing import Any, Literal, Sequence, cast

from playwright.sync_api import Locator, Page
from playwright.sync_api import TimeoutError as PwTimeout

from .models import AttrOperator, LocatorSpec
from .templates import TemplateSecurityError, has_placeholder, render

logger = logging.getLogger(__name__)

SelectorType = Literal["css", "xpath", "id", "name", "placeholder", "data-testid"]

#: Native Playwright arguments, never assembled into selector grammar.
_SEMANTIC_STRATEGIES = frozenset({"role", "label", "text", "placeholder", "testid"})

#: A literal CSS prefix followed by exactly one attribute test, covering the
#: WHOLE selector — e.g. `[name='{{x}}']` or `input[name='{{x}}']`.
#:
#: Full-match is what makes this safe. The prefix's character class excludes
#: braces, brackets and quotes, so it can hold no placeholder, no second attribute
#: test and no string literal: it is provably literal grammar. The attribute name,
#: operator and flags are fixed literals too, leaving the value as the only
#: position data can occupy.
#:
#: The value alternatives are deliberately strict. A permissive `.*?` between
#: optional quotes lets the closing quote be found arbitrarily far away, so
#: `[name='{{x}}'] [type='text']` — meant as a descendant selector — would parse
#: as one attribute whose value is `{{x}}'] [type='text`. Not injectable, but a
#: different selector than the one written, which is just as bad.
_ATTR_SELECTOR = re.compile(
    r"""(?P<prefix>[^{}\[\]'"]*?)
        \[\s*
        (?P<attr>[A-Za-z_][\w-]*)\s*
        (?P<op>[~|^$*]?=)\s*
        (?:
              '(?P<sval>[^']*)'      # single-quoted
            | "(?P<dval>[^"]*)"      # double-quoted
            | (?P<uval>[^"'\s\]]+)   # bare token, may not contain quotes
        )
        \s*\]""",
    re.VERBOSE,
)

_CSS_HEX_ESCAPES = (("\n", "\\a "), ("\r", "\\d "), ("\f", "\\c "))


def css_string(value: str) -> str:
    """Encode *value* as a double-quoted CSS string literal.

    Inside a double-quoted CSS string the only characters that can terminate or
    corrupt the string are the backslash, the quote, and raw newline/CR/form-feed
    (CSS Syntax L3 forbids them in strings). Escape exactly those and the result
    cannot break out, whatever the input.

    Notes:

    * Backslashes are doubled before escape sequences are inserted, otherwise the
      backslash we add would itself be doubled.
    * The trailing space in ``\\a `` is load-bearing: without it a following hex
      digit from the data merges into the escape (``"\\n" + "5"`` would become
      ``\\a5``, i.e. U+00A5).
    * NUL is rejected rather than escaped. CSS input preprocessing maps U+0000 to
      U+FFFD, so it is unrepresentable and ``[id="\\0nul"]`` would match an
      element whose id is ``"\\uFFFDnul"`` — a different element than intended.
    """
    if "\x00" in value:
        raise TemplateSecurityError(
            "template data contains a NUL (U+0000) character, which is not "
            "representable in a CSS string literal and cannot be escaped"
        )
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    for char, replacement in _CSS_HEX_ESCAPES:
        escaped = escaped.replace(char, replacement)
    return f'"{escaped}"'


def detect_selector_type(selector: str) -> SelectorType:
    """Auto-detect a legacy selector's type from its prefix.

    Only used for configuration that contains no placeholders, or to decide which
    safe strategy a templated selector normalizes into.
    """
    if selector.startswith("//"):
        return "xpath"
    if selector.startswith("#") and " " not in selector and "[" not in selector:
        return "id"
    if selector.startswith("[name="):
        return "name"
    if selector.startswith("[placeholder="):
        return "placeholder"
    if selector.startswith("[data-testid="):
        return "data-testid"
    return "css"


def resolve_selector(selector: str, selector_type: SelectorType | None = None) -> str:
    """Legacy string → Playwright selector string.

    Retained for configuration with no placeholders, where the input is trusted
    and the previous behaviour is preserved exactly.
    """
    stype = selector_type or detect_selector_type(selector)

    if stype == "xpath":
        return selector
    if stype == "id":
        return f"#{selector.lstrip('#')}"
    if stype in ("name", "placeholder", "data-testid"):
        return f"[{selector.strip('[]')}]"
    return selector


def normalize_selector(selector: str, selector_type: SelectorType | None = None) -> LocatorSpec:
    """Turn a legacy ``selector`` string into a :class:`LocatorSpec`.

    Raises:
        TemplateSecurityError: the selector contains a placeholder in a position
            that cannot be escaped.
    """
    if not has_placeholder(selector):
        # Trusted configuration: keep the original string and previous behaviour.
        stype = selector_type or detect_selector_type(selector)
        if stype == "xpath":
            return LocatorSpec(strategy="xpath", value=selector)
        return LocatorSpec(strategy="css", value=selector)

    stype = selector_type or detect_selector_type(selector)

    if stype == "xpath" or selector.lstrip().startswith("//"):
        raise TemplateSecurityError(
            "template variables are not allowed inside an XPath selector: XPath 1.0 "
            "string literals have no escape character. Use a locator with strategy "
            "'label', 'text', 'placeholder', 'testid' or 'role' instead."
        )

    if stype == "id":
        return LocatorSpec(strategy="id", value=selector[1:])

    match = _ATTR_SELECTOR.fullmatch(selector.strip())
    if match is None:
        raise TemplateSecurityError(
            f"template variables are only allowed in the attribute-value position of a "
            f"CSS selector (e.g. [name='{{{{field}}}}']), not in {selector!r}. CSS and "
            f"XPath are grammar, and data interpolated into grammar cannot be escaped. "
            f"Use a locator with strategy 'label', 'text', 'placeholder', 'testid' or "
            f"'role' — those pass the value to Playwright as an argument."
        )

    parts = match.groupdict()
    if has_placeholder(parts["attr"]):
        raise TemplateSecurityError("template variables are not allowed in a CSS attribute *name*")

    value = parts["sval"] if parts["sval"] is not None else parts["dval"]
    if value is None:
        value = parts["uval"]

    # Preserved verbatim: a trailing space in the author's prefix is a descendant
    # combinator (`#wrap [name=...]`) and dropping it would silently change the
    # selector into a compound one (`#wrap[name=...]`).
    prefix = (parts["prefix"] or "").lstrip()
    # The prefix's character class already excludes braces, so this is belt and
    # braces — but it is the property the whole rule rests on, so it is asserted.
    assert not has_placeholder(prefix), "literal prefix must never carry a placeholder"

    attribute = parts["attr"]
    if not prefix and attribute == "id":
        return LocatorSpec(strategy="id", value=value)
    if not prefix and attribute == "name":
        return LocatorSpec(strategy="name", value=value)
    # The regex only admits the six operators, so this cast is a formality — but
    # it is the same kind of assertion as the attribute-name check above: the rule
    # depends on the operator being a fixed literal, never on data.
    return LocatorSpec(
        strategy="attr",
        attr=attribute,
        op=cast(AttrOperator, parts["op"]),
        value=value,
        prefix=prefix,
    )


def build_locator_chain(step: Any) -> list[LocatorSpec]:
    """Primary + fallbacks for a step, as a single canonical candidate list.

    Works for both the legacy ``selector``/``selector_fallbacks`` form and the
    structured ``locator``/``locator_fallbacks`` form. Returns an empty list for
    steps that target no element at all (``navigate``, ``if``, ``scroll``, ...).
    """
    if step.locator is not None:
        return [step.locator, *step.locator_fallbacks]

    if not step.selector and not step.selector_fallbacks:
        return []

    chain = [normalize_selector(step.selector, step.selector_type)]
    for fallback in step.selector_fallbacks:
        chain.append(normalize_selector(fallback, None))
    return chain


def render_locator(spec: LocatorSpec, data: dict[str, Any]) -> LocatorSpec:
    """Substitute template variables into a locator's *argument* positions.

    Every field rendered here is an argument, not grammar: `css`/`xpath` values
    are refused outright if they carry a placeholder.
    """
    if spec.strategy in ("css", "xpath"):
        if has_placeholder(spec.value):
            raise TemplateSecurityError(
                f"template variables are not allowed in a raw {spec.strategy} locator "
                f"value: selector grammar cannot be escaped. Use strategy 'label', "
                f"'text', 'placeholder', 'testid' or 'role'."
            )
        return spec

    rendered = spec.model_copy(
        update={
            "value": render(spec.value, data) if spec.value is not None else None,
            "role": render(spec.role, data) if spec.role is not None else None,
            "name": render(spec.name, data) if spec.name is not None else None,
        }
    )
    if rendered.strategy not in _SEMANTIC_STRATEGIES:
        # id / name / attr land in a CSS attribute value. Validate it here so a
        # bad value is reported during rendering (TEMPLATE_ERROR) rather than
        # halfway through building a locator.
        css_string(rendered.value or "")
    return rendered


def resolve_locator(page: Page, spec: LocatorSpec) -> Locator:
    """Build a Playwright locator from a rendered spec.

    Raises:
        Error: the selector engine rejected the result (INVALID_SELECTOR).
    """
    strategy = spec.strategy
    value = spec.value or ""

    if strategy == "css":
        return page.locator(value)
    if strategy == "xpath":
        return page.locator(f"xpath={value}")
    if strategy in ("id", "name"):
        return page.locator(f"[{strategy}={css_string(value)}]")
    if strategy == "attr":
        return page.locator(f"{spec.prefix}[{spec.attr}{spec.op}{css_string(value)}]")

    if strategy == "role":
        # `role` is free text from the config. Playwright validates it and raises
        # InvalidSelectorError for an unknown role, which fails closed — the run
        # reports INVALID_SELECTOR rather than matching something unintended.
        return page.get_by_role(cast(Any, spec.role or ""), name=spec.name, exact=spec.exact)
    if strategy == "label":
        return page.get_by_label(value, exact=spec.exact)
    if strategy == "text":
        return page.get_by_text(value, exact=spec.exact)
    if strategy == "placeholder":
        return page.get_by_placeholder(value, exact=spec.exact)
    if strategy == "testid":
        return page.get_by_test_id(value)

    raise ValueError(f"unsupported locator strategy: {strategy!r}")


def describe_locator(spec: LocatorSpec) -> str:
    """Short human-readable form, for logs and diagnostics."""
    if spec.strategy == "role":
        suffix = f" name={spec.name!r}" if spec.name else ""
        return f"role={spec.role!r}{suffix}"
    if spec.strategy == "attr":
        return f"{spec.prefix}[{spec.attr}{spec.op}{spec.value!r}]"
    return f"{spec.strategy}={spec.value!r}"


def find_locator(
    page: Page, specs: Sequence[LocatorSpec], timeout_ms: int = 5000
) -> Locator | None:
    """Try each candidate in order; return the first match, or None.

    Only a *timeout* advances to the next candidate. A structural failure —
    invalid selector syntax, closed target — propagates immediately instead of
    being silently swallowed: it means the configuration is malformed, and
    falling through to a backup would hide that and make the chain's behaviour
    depend on which candidate happened to be broken.
    """
    for spec in specs:
        loc = resolve_locator(page, spec).first
        try:
            loc.wait_for(state="attached", timeout=min(timeout_ms, 3000))
            if loc.count() > 0:
                return loc
        except PwTimeout:
            logger.debug("Locator %s did not match, trying next.", describe_locator(spec))
            continue
    return None


def find_element(
    page: Page,
    selector: str,
    fallbacks: list[str] | None = None,
    selector_type: SelectorType | None = None,
    timeout_ms: int = 5000,
) -> Locator | None:
    """Legacy string-based entry point; see :func:`find_locator`."""
    chain = [normalize_selector(selector, selector_type)]
    chain.extend(normalize_selector(fallback, None) for fallback in (fallbacks or []))
    return find_locator(page, chain, timeout_ms)
