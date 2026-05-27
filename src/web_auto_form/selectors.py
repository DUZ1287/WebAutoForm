"""Selector resolution: auto-detect type, convert to Playwright selector, fallback chain."""

from __future__ import annotations

import logging
from typing import Literal

from playwright.sync_api import Locator, Page
from playwright.sync_api import TimeoutError as PwTimeout

logger = logging.getLogger(__name__)

SelectorType = Literal["css", "xpath", "id", "name", "placeholder", "data-testid"]


def detect_selector_type(selector: str) -> SelectorType:
    """Auto-detect selector type based on prefix heuristics."""
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
    """Convert a raw selector string to a Playwright-compatible selector."""
    stype = selector_type or detect_selector_type(selector)

    if stype == "xpath":
        return selector
    if stype == "id":
        return f"#{selector.lstrip('#')}"
    if stype == "name":
        inner = selector.strip("[]")
        return f"[{inner}]"
    if stype == "placeholder":
        inner = selector.strip("[]")
        return f"[{inner}]"
    if stype == "data-testid":
        inner = selector.strip("[]")
        return f"[{inner}]"
    return selector


def find_element(
    page: Page,
    selector: str,
    fallbacks: list[str] | None = None,
    selector_type: SelectorType | None = None,
    timeout_ms: int = 5000,
) -> Locator | None:
    """Try primary selector then each fallback; return first match or None."""
    candidates = [selector] + (fallbacks or [])

    for cand in candidates:
        resolved = resolve_selector(cand, selector_type if cand == selector else None)
        try:
            loc = page.locator(resolved).first
            loc.wait_for(state="attached", timeout=min(timeout_ms, 3000))
            if loc.count() > 0:
                return loc
        except (PwTimeout, Exception):
            logger.debug("Selector %r did not match, trying next.", resolved)
            continue
    return None
