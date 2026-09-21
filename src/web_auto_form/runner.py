"""Core step executor: exception containment, retry ownership, failure policy.

Execution contract
------------------
1. An action handler performs exactly one attempt. It never retries and never
   decides policy.
2. The Runner is the single owner of retry. ``max_retries`` counts *additional*
   attempts on top of the first, so ``max_retries=2`` means at most 3 attempts.
3. Failures are classified into an :class:`~web_auto_form.errors.ErrorCode`.
   ``retryable`` is a property of that code; whether a retry happens is a policy
   decision made by :meth:`Runner._should_retry`.
4. Control-flow intent (:class:`StepOutcome`) propagates out of nested if/else,
   so a hard failure inside ``then`` stops the workflow, not just the branch.
5. No browser failure escapes this module. Everything becomes a structured
   :class:`StepResult`, and :meth:`Runner.run` always returns a JSON-ready dict.
"""

from __future__ import annotations

import logging
import time
import traceback
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Sequence

from .actions import ACTION_REGISTRY
from .actions.base import ActionContext, StepResult, failed
from .actions.if_branch import evaluate_condition
from .browser import BrowserManager
from .errors import ErrorCode, ErrorInfo, classify_exception, error_entry
from .models import StepConfig, WebAutoFormConfig
from .redact import redact_text
from .selectors import build_locator_chain, normalize_selector, render_locator, resolve_locator
from .templates import TemplateSecurityError, has_placeholder, render_dict

logger = logging.getLogger(__name__)

MAX_NESTING_DEPTH = 3

#: Fields the locator layer owns; excluded from blanket template rendering.
_LOCATOR_FIELDS = (
    "selector",
    "selector_type",
    "selector_fallbacks",
    "locator",
    "locator_fallbacks",
)

ActionFn = Callable[[ActionContext], StepResult]


def failed_output(
    errors: list[dict[str, Any]], consent_statement: str | None = None
) -> dict[str, Any]:
    """Output shape for a failure that never reached the step engine.

    Kept here, next to `Runner._build_output`, so every entry point (library,
    CLI, MCP) returns the same keys.
    """
    return {
        "status": "failed",
        "consent_logged": consent_statement,
        "aborted": True,
        "steps_executed": 0,
        "steps_skipped": 0,
        "steps_failed": 0,
        "results": [],
        "step_screenshots": [],
        "extracted": {},
        "final_screenshot": None,
        "debug_artifacts": None,
        "errors": errors,
    }


# ── Diagnostics JS snippet ────────────────────────────────────────────
# Extracts visible form elements for Agent auto-repair when a step fails.
_DIAGNOSTICS_JS = """() => {
  const selector =
    'input, select, textarea, button, ' +
    '[role="button"], [role="radio"], [role="checkbox"], label';
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


def _reject_unescapable_interpolation(step: StepConfig) -> None:
    """Forbid placeholders in fields whose contents reach a parser we cannot escape.

    Two fields interpolate into something other than a CSS selector:

    * ``wait type=function`` — ``value`` is JavaScript handed to
      ``page.wait_for_function()`` and evaluated in page context on a poll loop,
      so untrusted data there is script execution, not a bad selector.
    * ``if`` + ``operator=matches_regex`` — ``expected_value`` becomes the regex
      *pattern*; a crafted value causes catastrophic backtracking that nothing
      can interrupt, since the 300s budget is only checked between steps.

    Both are hard configuration errors rather than warnings: the failure mode is
    a security boundary, not a flaky selector.
    """
    if step.action == "wait" and step.type == "function" and has_placeholder(step.value):
        raise TemplateSecurityError(
            "template variables are not allowed in `wait type=function` value: it is "
            "JavaScript evaluated in page context and cannot be escaped. Use a "
            "selector-based wait, or a condition that needs no page data."
        )

    condition = step.condition
    if (
        condition is not None
        and condition.operator == "matches_regex"
        and has_placeholder(condition.expected_value)
    ):
        raise TemplateSecurityError(
            "template variables are not allowed in `expected_value` when "
            "operator=matches_regex: the value becomes the regex pattern and "
            "untrusted input can cause catastrophic backtracking. Use a literal "
            "pattern, or compare with `contains` instead."
        )


class StepOutcome(str, Enum):
    """Control-flow intent returned by step execution, nested branches included."""

    CONTINUE = "continue"
    ABORT = "abort"


class Runner:
    """Executes a web_auto_form configuration step by step."""

    def __init__(self, config: WebAutoFormConfig) -> None:
        self.config = config
        self.browser_mgr = BrowserManager(config.options)
        self.results: list[StepResult] = []
        self.errors: list[dict[str, Any]] = []
        self.step_screenshots: list[dict[str, Any]] = []
        self.extracted: dict[str, Any] = {}
        self.final_screenshot: str | None = None
        self.debug_artifacts: str | None = None
        self.aborted = False
        self._total_start: float = 0.0

    # ── Top level ─────────────────────────────────────────────────────

    def run(self) -> dict[str, Any]:
        """Execute the full configuration and return the output dict.

        Never raises for browser/execution failures: those are contained and
        reported as ``status: "failed"`` with a populated ``errors`` list.
        """
        self._total_start = time.monotonic()

        logger.info("Consent: %s", self.config.consent_statement)
        if not self.config.options.headless:
            print(f"\n[web_auto_form] Consent: {self.config.consent_statement}\n")

        try:
            page = self.browser_mgr.launch()
        except Exception as exc:
            # Browser could not start at all — nothing else can run. launch() may
            # already have started Playwright before failing, so tear it down:
            # leaving the sync driver alive poisons later runs in the same process.
            self._abort_workflow(classify_exception(exc, "launch"))
            self.browser_mgr.close()
            return self._build_output()

        try:
            page.goto(self.config.url, wait_until="domcontentloaded", timeout=30000)

            for idx, step in enumerate(self.config.steps):
                if self._execute_step(step, idx, depth=0) is StepOutcome.ABORT:
                    self.aborted = True
                    break

            self.extracted = self._extract(page)
            if self.config.extract_schema.screenshot:
                self.final_screenshot = self.browser_mgr.screenshot(full_page=True)
            if self.config.options.debug:
                self.debug_artifacts = self._debug_path()
        except Exception as exc:
            # Containment boundary for anything outside an individual step
            # (initial navigation, extraction, screenshots).
            self._abort_workflow(classify_exception(exc, "run"))
        finally:
            if not self.config.options.keep_open:
                self.browser_mgr.close()

        return self._build_output()

    def _build_output(self) -> dict[str, Any]:
        steps_skipped = sum(1 for r in self.results if r.status == "skipped")
        steps_failed = sum(1 for r in self.results if r.status == "failed")
        steps_executed = len(self.results) - steps_skipped

        if self.aborted:
            status = "failed"
        elif steps_failed > 0:
            status = "partial"
        else:
            status = "success"

        return {
            "status": status,
            "consent_logged": self.config.consent_statement,
            "aborted": self.aborted,
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
                    **({"error_code": r.error_code} if r.error_code else {}),
                    **({"retryable": r.retryable} if r.status == "failed" else {}),
                    **({"diagnostics": r.diagnostics} if r.diagnostics else {}),
                }
                for r in self.results
            ],
            "step_screenshots": self.step_screenshots,
            "extracted": self.extracted,
            "final_screenshot": self.final_screenshot,
            "debug_artifacts": self.debug_artifacts,
            "errors": self.errors,
        }

    def _remaining_budget_ms(self) -> int:
        """Milliseconds left in the workflow budget; 0 once it is spent."""
        elapsed_ms = (time.monotonic() - self._total_start) * 1000
        return max(0, int(self.config.options.max_total_ms - elapsed_ms))

    # ── Step execution ────────────────────────────────────────────────

    def _execute_step(self, step: StepConfig, index: int, depth: int) -> StepOutcome:
        """Execute one step (one attempt per retry) and return the control intent."""
        if self._remaining_budget_ms() <= 0:
            info = ErrorInfo(
                ErrorCode.TIMEOUT,
                f"total execution time exceeded {self.config.options.max_total_ms}ms limit",
            )
            result = failed(index, step.action, info.code, info.message)
            self._attach_diagnostics(result)
            self._record_result(result, step)
            self._abort_workflow(info)
            return StepOutcome.ABORT

        try:
            rendered = self._render_step(step, self.config.data)
        except Exception as exc:
            return self._failure_outcome(
                step,
                index,
                failed(
                    index,
                    step.action,
                    ErrorCode.TEMPLATE_ERROR,
                    f"template render failed: {classify_exception(exc).message}",
                ),
            )

        if rendered.action == "if":
            return self._execute_if(rendered, index, depth)

        action_fn = ACTION_REGISTRY.get(rendered.action)
        if action_fn is None:
            return self._failure_outcome(
                rendered,
                index,
                failed(
                    index,
                    rendered.action,
                    ErrorCode.INTERNAL_ERROR,
                    f"unknown action: {rendered.action}",
                ),
            )

        max_retries = (
            rendered.max_retries
            if rendered.max_retries is not None
            else self.config.options.max_retries
        )
        retry_on: Sequence[Any] = (
            rendered.retry_on if rendered.retry_on is not None else self.config.options.retry_on
        )

        attempt = 0
        while True:
            result = self._attempt(action_fn, rendered, index)

            if result.status == "ok":
                result.retries = attempt
                self._record_result(result, rendered)
                self._post_step(index, rendered)
                return StepOutcome.CONTINUE

            if self._should_retry(rendered, result, attempt, max_retries, retry_on):
                attempt += 1
                logger.info(
                    "Step %d (%s): retry %d/%d after %s",
                    index,
                    rendered.action,
                    attempt,
                    max_retries,
                    result.error_code,
                )
                time.sleep(self.config.options.step_delay_ms / 1000.0)
                continue

            result.retries = attempt
            return self._failure_outcome(rendered, index, result)

    def _execute_if(self, step: StepConfig, index: int, depth: int) -> StepOutcome:
        """Evaluate an if condition and run the chosen branch.

        An ABORT returned by any nested step propagates straight out, so the rest
        of the branch and every later top-level step are skipped.
        """
        if depth >= MAX_NESTING_DEPTH:
            return self._failure_outcome(
                step,
                index,
                failed(
                    index,
                    "if",
                    ErrorCode.INTERNAL_ERROR,
                    f"max nesting depth ({MAX_NESTING_DEPTH}) exceeded at step {index}",
                ),
            )

        ctx = ActionContext(
            page=self.browser_mgr.page,
            step=step,
            options=self.config.options,
            step_index=index,
            data=self.config.data,
            remaining_budget_ms=self._remaining_budget_ms(),
        )

        try:
            condition_result = evaluate_condition(ctx)
        except Exception as exc:
            info = classify_exception(exc, "if")
            return self._failure_outcome(
                step,
                index,
                failed(index, "if", info.code, f"condition evaluation failed: {info.message}"),
            )

        branch = step.then_steps if condition_result else step.else_steps

        self.results.append(
            StepResult(
                step_index=index,
                action="if",
                status="ok",
                value=(
                    f"condition={condition_result}, "
                    f"branch={'then' if condition_result else 'else'}"
                ),
            )
        )

        for sub_step in branch:
            if self._execute_step(sub_step, index, depth + 1) is StepOutcome.ABORT:
                return StepOutcome.ABORT

        return StepOutcome.CONTINUE

    # ── Exception boundary ────────────────────────────────────────────

    def _attempt(self, action_fn: ActionFn, step: StepConfig, index: int) -> StepResult:
        """Run one attempt behind the exception boundary.

        Known browser failures become structured failure results. Anything
        unexpected becomes INTERNAL_ERROR and is logged with its traceback —
        never silently swallowed.
        """
        ctx = ActionContext(
            page=self.browser_mgr.page,
            step=step,
            options=self.config.options,
            step_index=index,
            data=self.config.data,
            remaining_budget_ms=self._remaining_budget_ms(),
        )

        try:
            return action_fn(ctx)
        except Exception as exc:
            info = classify_exception(exc, step.action)
            logger.debug(
                "Step %d (%s) raised %s: %s",
                index,
                step.action,
                type(exc).__name__,
                info.message,
            )
            result = failed(index, step.action, info.code, info.message)
            if info.code is ErrorCode.INTERNAL_ERROR:
                logger.error("Step %d (%s): internal error", index, step.action, exc_info=True)
                if self.config.options.debug:
                    result.diagnostics = {"traceback": traceback.format_exc()}
            return result

    # ── Retry policy (single owner) ───────────────────────────────────

    def _should_retry(
        self,
        step: StepConfig,
        result: StepResult,
        attempt: int,
        max_retries: int,
        retry_on: Sequence[Any],
    ) -> bool:
        """Decide whether another attempt is warranted.

        ``attempt`` is the 0-based index of the attempt that just failed, so
        ``attempt >= max_retries`` means the budget is spent.
        """
        if attempt >= max_retries:
            return False
        # An explicit per-step `on_fail: retry` is an author instruction and
        # overrides the intrinsic-retryability gate.
        if step.on_fail == "retry":
            return True
        if not result.retryable or not result.error_code:
            return False
        return result.error_code in retry_on

    # ── Failure policy ────────────────────────────────────────────────

    def _failure_outcome(self, step: StepConfig, index: int, result: StepResult) -> StepOutcome:
        """Attach diagnostics, apply failure policy, record, and return the intent."""
        self._attach_diagnostics(result)
        outcome = self._apply_failure_policy(step, index, result)
        self._record_result(result, step)
        if outcome is StepOutcome.CONTINUE and result.status == "skipped":
            self._post_step(index, step)
        return outcome

    def _apply_failure_policy(
        self, step: StepConfig, index: int, result: StepResult
    ) -> StepOutcome:
        """Map a failed step onto a control-flow intent.

        Precedence:

        1. ``optional: true``  -> recorded as ``skipped``, workflow continues.
           ``on_skip: abort`` is the exception and aborts the workflow.
        2. ``on_fail: continue`` -> recorded as ``failed``, workflow continues
           (the workflow ends up ``partial``).
        3. otherwise (``abort``, or ``retry`` once the budget is spent) ->
           recorded as ``failed``, workflow aborts immediately.
        """
        label = f"Step {index} ({step.action})"

        if step.optional:
            if step.on_skip == "abort":
                result.status = "failed"
                self.errors.append(
                    self._error_entry(result, index, step, note="optional step, on_skip=abort")
                )
                logger.error("%s: aborting workflow — %s", label, result.error)
                return StepOutcome.ABORT

            if step.on_skip == "set_default":
                logger.info("%s: skipped, using default value %r", label, step.value)
            else:
                logger.warning("%s: skipped — %s", label, result.error)
            result.status = "skipped"
            return StepOutcome.CONTINUE

        result.status = "failed"
        self.errors.append(self._error_entry(result, index, step))

        if step.on_fail == "continue":
            logger.warning("%s: failed, continuing — %s", label, result.error)
            return StepOutcome.CONTINUE

        logger.error("%s: aborting workflow — %s", label, result.error)
        return StepOutcome.ABORT

    @staticmethod
    def _error_entry(
        result: StepResult, index: int, step: StepConfig, note: str | None = None
    ) -> dict[str, Any]:
        """One structured entry for the output ``errors`` array."""
        return error_entry(
            ErrorCode(result.error_code) if result.error_code else ErrorCode.UNKNOWN,
            result.error or "step failed",
            step=index,
            action=step.action,
            retryable=result.retryable or None,
            note=note,
        )

    def _abort_workflow(self, info: ErrorInfo) -> None:
        """Record a workflow-level fatal error; the run will report 'failed'."""
        self.aborted = True
        self.errors.append(error_entry(info.code, info.message))

    # ── Rendering, recording, diagnostics ─────────────────────────────

    def _render_step(self, step: StepConfig, data: dict[str, Any]) -> StepConfig:
        """Render a step and normalize its locator into the canonical chain.

        Locator fields are deliberately *not* blanket-rendered: which substitution
        rule applies depends on the locator's strategy, so they go through
        `render_locator` instead. Substituting first and asking questions later is
        exactly how data ends up in a grammar position. The `if` condition's
        selector is left unrendered for the same reason — `evaluate_condition`
        resolves it through the same safe path.

        The result always carries `locator`/`locator_fallbacks`, so downstream
        code has a single representation to handle.
        """
        _reject_unescapable_interpolation(step)

        raw = step.model_dump(by_alias=True, exclude_none=False)
        for key in _LOCATOR_FIELDS:
            raw.pop(key, None)

        condition = raw.get("condition")
        condition_selector = None
        if isinstance(condition, dict):
            condition_selector = condition.pop("selector", None)

        rendered = render_dict(raw, data) if data else raw

        if isinstance(rendered.get("condition"), dict):
            rendered["condition"]["selector"] = condition_selector

        chain = [render_locator(spec, data) for spec in build_locator_chain(step)]
        rendered["locator"] = chain[0].model_dump() if chain else None
        rendered["locator_fallbacks"] = [spec.model_dump() for spec in chain[1:]]

        return StepConfig(**rendered)

    def _record_result(self, result: StepResult, step: StepConfig) -> None:
        """Record step result and optional screenshot."""
        if step.screenshot:
            try:
                result.screenshot = self.browser_mgr.screenshot()
            except Exception:
                pass
        self.results.append(result)

    def _attach_diagnostics(self, result: StepResult) -> None:
        """Capture screenshot + page elements, merging with anything already set."""
        if not self.config.options.diagnose_on_failure:
            return
        captured = self._capture_diagnostics()
        if captured:
            result.diagnostics = {**(result.diagnostics or {}), **captured}

    def _capture_diagnostics(self) -> dict:
        """Capture screenshot + visible form elements for Agent self-repair."""
        diagnostics: dict[str, Any] = {}
        try:
            diagnostics["screenshot"] = self.browser_mgr.screenshot()
        except Exception:
            pass
        try:
            raw = self.browser_mgr.page.evaluate(_DIAGNOSTICS_JS)
            diagnostics["form_elements"] = raw[:60] if isinstance(raw, list) and raw else []
        except Exception as exc:
            # Never let a broken diagnostics snippet look like "no elements on
            # the page" — that would silently mislead the Agent's self-repair.
            logger.warning("Failed to collect form elements for diagnostics: %s", exc)
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
                self.browser_mgr.save_debug(self._debug_path(), index)
            except Exception as e:
                logger.debug("Failed to save debug artifacts: %s", e)

        time.sleep(self.config.options.step_delay_ms / 1000.0)

    def _debug_path(self) -> str:
        return self.config.options.debug_output_path.replace(
            "<timestamp>", datetime.now().strftime("%Y%m%d_%H%M%S")
        )

    def _extract(self, page: object) -> dict[str, Any]:
        """Extract structured data per extract_schema."""
        schema = self.config.extract_schema
        if not schema.fields:
            return {}

        result: dict[str, Any] = {}
        for field in schema.fields:
            try:
                # Same safe path as step locators: extract selectors used to be
                # rendered with a bare substitution and resolved directly, which
                # made them an unguarded injection route.
                spec = render_locator(normalize_selector(field.selector), self.config.data)
                loc = resolve_locator(page, spec).first  # type: ignore[arg-type]

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
