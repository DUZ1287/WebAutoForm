"""Playwright browser lifecycle management."""

from __future__ import annotations

import base64
import logging
from typing import Any

from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright

from .models import OptionsConfig

logger = logging.getLogger(__name__)


class BrowserManager:
    """Manages Playwright browser, context, and page lifecycle."""

    def __init__(self, options: OptionsConfig) -> None:
        self._options = options
        self._pw: Any = None
        self._browser: Browser | None = None
        self._context: BrowserContext | None = None
        self._page: Page | None = None

    def launch(self) -> Page:
        """Launch browser and return the active page."""
        self._pw = sync_playwright().start()
        launch_args: dict[str, Any] = {
            "headless": self._options.headless,
        }
        if self._options.sandbox:
            launch_args["args"] = ["--no-sandbox", "--disable-setuid-sandbox"]

        self._browser = self._pw.chromium.launch(**launch_args)
        context_args: dict[str, Any] = {
            "viewport": {
                "width": self._options.viewport_width,
                "height": self._options.viewport_height,
            },
            "locale": self._options.locale,
        }
        if self._options.user_agent:
            context_args["user_agent"] = self._options.user_agent

        self._context = self._browser.new_context(**context_args)
        self._page = self._context.new_page()
        return self._page

    @property
    def page(self) -> Page:
        if self._page is None:
            raise RuntimeError("Browser not launched. Call launch() first.")
        return self._page

    def screenshot(self, full_page: bool = False) -> str:
        """Capture screenshot and return base64-encoded PNG."""
        png_bytes = self.page.screenshot(full_page=full_page)
        return base64.b64encode(png_bytes).decode("ascii")

    def save_debug(self, path: str, step_index: int) -> None:
        """Save page HTML and screenshot for debug purposes."""
        import os

        os.makedirs(path, exist_ok=True)
        html = self.page.content()
        with open(os.path.join(path, f"step_{step_index}.html"), "w", encoding="utf-8") as f:
            f.write(html)
        self.page.screenshot(path=os.path.join(path, f"step_{step_index}.png"), full_page=True)

    def close(self) -> None:
        """Close page, context, browser, and stop Playwright."""
        try:
            if self._page and not self._page.is_closed():
                self._page.close()
        except Exception:
            pass
        try:
            if self._context:
                self._context.close()
        except Exception:
            pass
        try:
            if self._browser:
                self._browser.close()
        except Exception:
            pass
        try:
            if self._pw:
                self._pw.stop()
        except Exception:
            pass
