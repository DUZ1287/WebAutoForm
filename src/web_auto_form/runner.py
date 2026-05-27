"""Core step executor with retry logic, template rendering, and error handling."""

from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any

from .actions import ACTION_REGISTRY
from .actions.base import ActionContext, StepResult
from .actions.if_branch import evaluate_condition
from .browser import BrowserManager
from .models import StepConfig, WebAutoFormConfig
from .redact import redact_text
from .templates import render, render_dict

logger = logging.getLogger(__name__)

MAX_NESTING_DEPTH = 3

# ── Diagnostics JS snippet ────────────────────────────────────────────
# Extracts visible form elements for Agent auto-repair when a step fails.
_DIAGNOSTICS_JS = """() => {
  const selector = (
    'input, select, textarea, button, '
    '[role="button"], [role="radio"], [role="checkbox"], label'
  );
  const els = document.querySelectorAll(selector);
  const seen = new Set();
  const items = [];
  els.forEach(el => {
    const tag = el.tagName.toLowerCase();
    const type = el.type || '';
    const name = el.name || el.getAttribute('name') || '';
    const id = el.id || '';
    const placeholder = el.placeholder || el.getAttribute('placeholder') || '';
    const text = (el.textContent || '').trim().slice(0, 60);
    const ariaLabel = el.getAttribute('aria-label') || '';
    const dataTestid = el.getAttribute('data-testid') || '';
    const classes = (el.className || '').toString().trim().slice(0, 80);
    const visible = el.offsetParent !== null;
    const key = tag + '|' + type + '|' + name + '|' + id + '|' + placeholder;
    if (!seen.has(key)) {
      seen.add(key);
      items.push({tag, type, name, id, placeholder, text, ariaLabel, dataTestid, classes, visible});
    }
  });
  return items;
}"""


class Runner:
    """Executes a web_auto_form configuration step by step."""

    def __init__(self, config: WebAutoFormConfig) -> None:
        self.config = config
        self.browser_mgr = BrowserManager(config.options)
        self.results: list[StepResult] = []
        self.errors: list[str] = []
        self.step_screenshots: list[dict[str, Any]] = []
        self._total_start: float = 0.0

    def run(self) -> dict[str, Any]:
        """Execute the full configuration and return the output dict."""
        self._total_start = time.monotonic()

        logger.info("Consent: %s", self.config.consent_statement)
        if not self.config.options.headless:
            print(f"\n[web_auto_form] Consent: {self.config.consent_statement}\n")

        page = self.browser_mgr.launch()

        try:
            page.goto(self.config.url, wait_until="domcontentloaded", timeout=30000)

            for idx, step in enumerate(self.config.steps):
                self._execute_step(step, idx, depth=0)

            extracted = self._extract(page)
            final_screenshot = None
            if self.config.extract_schema.screenshot:
                final_screenshot = self.browser_mgr.screenshot(full_page=True)

            debug_artifacts = None
            if self.config.options.debug:
                debug_artifacts = self.config.options.debug_output_path.replace(
                    "<timestamp>", datetime.now().strftime("%Y%m%d_%H%M%S")
                )

        finally:
            if not self.config.options.keep_open:
                self.browser_mgr.close()

        steps_executed = len([r for r in self.results if r.status != "skipped"])
        steps_skipped = len([r for r in self.results if r.status == "skipped"])
        steps_failed = len([r for r in self.results if r.status == "failed"])

        status = "success"
        if steps_failed > 0 and steps_executed == steps_failed:
            status = "failed"
        elif steps_failed > 0:
            status = "partial"

        return {
            "status": status,
            "consent_logged": self.config.consent_statement,
            "steps_executed": steps_executed,
            "steps_skipped": steps_skipped,
            "steps_failed": steps_failed,
            "results": [
                {
                    "step": r.step_index,
                    "action": r.action,
                    "status": r.status,
                    "duration_ms": r.duration_ms,
                    **({"retries": r.retries} if r.retries > 0 else {}),
                    **({"error": r.error} if r.error else {}),
                    **({"diagnostics": r.diagnostics} if r.diagnostics else {}),
                }
                for r in self.results
            ],
            "step_screenshots": self.step_screenshots,
            "extracted": extracted,
            "final_screenshot": final_screenshot,
            "debug_artifacts": debug_artifacts,
            "errors": self.errors,
        }

    def _execute_step(self, step: StepConfig, index: int, depth: int) -> None:
        """Execute a single step with retry logic and optional handling."""
        elapsed = time.monotonic() - self._total_start
        if elapsed > 300:
            self.errors.append("Total execution time exceeded 300s limit")
            return

        # Render templates in step fields
        data = self.config.data
        rendered_step = self._render_step(step, data)

        if rendered_step.action == "if":
            self._execute_if(rendered_step, index, depth)
            return

        action_fn = ACTION_REGISTRY.get(rendered_step.action)
        if action_fn is None:
            self.errors.append(f"Unknown action: {rendered_step.action}")
            return

        ctx = ActionContext(
            page=self.browser_mgr.page,
            step=rendered_step,
            options=self.config.options,
            step_index=index,
            data=data,
        )

        max_retries = rendered_step.max_retries or self.config.options.max_retries
        retry_on = rendered_step.retry_on or self.config.options.retry_on

        for attempt in range(max_retries + 1):
            result = action_fn(ctx)

            if result.status == "ok":
                result.retries = attempt
                self._record_result(result, rendered_step)
                self._post_step(index, rendered_step)
                return

            if result.status == "failed" and rendered_step.optional:
                skip_behavior = rendered_step.on_skip
                if skip_behavior == "abort":
                    self.errors.append(
                        f"Step {index} ({rendered_step.action}): optional step aborted"
                    )
                    if self.config.options.diagnose_on_failure:
                        result.diagnostics = self._capture_diagnostics()
                    self._record_result(result, rendered_step)
                    return
                elif skip_behavior == "set_default":
                    logger.info("Step %d: using default value %r", index, rendered_step.value)
                    result.status = "skipped"
                    self._record_result(result, rendered_step)
                    self._post_step(index, rendered_step)
                    return
                else:  # log
                    logger.warning(
                        "Step %d (%s): skipped — %s", index, rendered_step.action, result.error
                    )
                    result.status = "skipped"
                    self._record_result(result, rendered_step)
                    self._post_step(index, rendered_step)
                    return

            if attempt < max_retries and _is_retryable(result.error, retry_on):
                logger.info("Step %d: retry %d/%d", index, attempt + 1, max_retries)
                time.sleep(self.config.options.step_delay_ms / 1000.0)
                continue

            if self.config.options.diagnose_on_failure:
                result.diagnostics = self._capture_diagnostics()
            self._record_result(result, rendered_step)
            return

    def _execute_if(self, step: StepConfig, index: int, depth: int) -> None:
        """Evaluate if condition and execute then/else branches."""
        if depth >= MAX_NESTING_DEPTH:
            self.errors.append(f"Max nesting depth ({MAX_NESTING_DEPTH}) exceeded at step {index}")
            return

        ctx = ActionContext(
            page=self.browser_mgr.page,
            step=step,
            options=self.config.options,
            step_index=index,
            data=self.config.data,
        )

        condition_result = evaluate_condition(ctx)
        branch = step.then_steps if condition_result else step.else_steps

        self.results.append(
            StepResult(
                step_index=index,
                action="if",
                status="ok",
                value=f"condition={condition_result}, branch={'then' if condition_result else 'else'}",
            )
        )

        for sub_idx, sub_step in enumerate(branch):
            self._execute_step(sub_step, index, depth + 1)

    def _render_step(self, step: StepConfig, data: dict[str, Any]) -> StepConfig:
        """Render template variables in all string fields of a step."""
        if not data:
            return step

        raw = step.model_dump(by_alias=True, exclude_none=False)
        rendered = render_dict(raw, data)
        return StepConfig(**rendered)

    def _record_result(self, result: StepResult, step: StepConfig) -> None:
        """Record step result and optional screenshot."""
        if step.screenshot:
            try:
                result.screenshot = self.browser_mgr.screenshot()
            except Exception:
                pass
        self.results.append(result)

    def _capture_diagnostics(self) -> dict:
        """Capture screenshot + visible form elements for Agent self-repair."""
        diagnostics: dict[str, Any] = {}
        try:
            diagnostics["screenshot"] = self.browser_mgr.screenshot()
        except Exception:
            pass
        try:
            raw = self.browser_mgr.page.evaluate(_DIAGNOSTICS_JS)  # type: ignore[union-attr]
            if isinstance(raw, list) and len(raw) > 0:
                diagnostics["form_elements"] = raw[:60]
            else:
                diagnostics["form_elements"] = []
        except Exception:
            diagnostics["form_elements"] = []
        return diagnostics

    def _post_step(self, index: int, step: StepConfig) -> None:
        """Apply step delay and save debug artifacts."""
        if step.screenshot:
            self.step_screenshots.append(
                {
                    "step": index,
                    "screenshot": self.results[-1].screenshot if self.results else None,
                }
            )

        if self.config.options.debug:
            try:
                debug_path = self.config.options.debug_output_path.replace(
                    "<timestamp>", datetime.now().strftime("%Y%m%d_%H%M%S")
                )
                self.browser_mgr.save_debug(debug_path, index)
            except Exception as e:
                logger.debug("Failed to save debug artifacts: %s", e)

        time.sleep(self.config.options.step_delay_ms / 1000.0)

    def _extract(self, page: object) -> dict[str, Any]:
        """Extract structured data per extract_schema."""
        schema = self.config.extract_schema
        if not schema.fields:
            return {}

        result: dict[str, Any] = {}
        for field in schema.fields:
            try:
                selector = render(field.selector, self.config.data)
                from .selectors import resolve_selector

                resolved = resolve_selector(selector)
                loc = page.locator(resolved).first  # type: ignore[union-attr]

                if field.attribute == "text":
                    raw = loc.text_content() or ""
                elif field.attribute == "innerHTML":
                    raw = loc.inner_html()
                elif field.attribute == "value":
                    raw = loc.input_value()
                else:
                    raw = loc.get_attribute(field.attribute) or ""

                should_redact = (
                    field.redact if field.redact is not None else self.config.options.redact_pii
                )
                if should_redact:
                    raw = redact_text(raw)

                result[field.name] = raw
            except Exception as e:
                logger.warning("Extract field %r failed: %s", field.name, e)
                result[field.name] = None

        return result


def _is_retryable(error: str | None, retry_on: list[str]) -> bool:
    """Check if an error is retryable based on the retry_on list."""
    if not error:
        return False
    error_lower = error.lower()
    if "NETWORK_ERROR" in retry_on and ("network" in error_lower or "connection" in error_lower):
        return True
    if "TIMEOUT" in retry_on and "timeout" in error_lower:
        return True
    if "NAVIGATION_FAILED" in retry_on and "navigation" in error_lower:
        return True
    return False
