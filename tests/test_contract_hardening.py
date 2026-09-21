"""Phase 1.1: the Agent-facing execution contract.

Covers the boundary between "the caller gave us something unusable" and "the
execution engine failed" — both must arrive as a structured observation, never
as an exception escaping `run()` or the MCP tool handler.
"""

from __future__ import annotations

import importlib.util
import json
import time
from pathlib import Path
from typing import Any

import pytest

from web_auto_form import run, run_from_path
from web_auto_form.actions import ACTION_REGISTRY
from web_auto_form.actions.base import ActionContext
from web_auto_form.actions.navigate import run_navigate
from web_auto_form.actions.scroll import run_scroll
from web_auto_form.actions.wait import run_wait
from web_auto_form.models import OptionsConfig, StepConfig
from web_auto_form.runner import (
    StepOutcome,
    _reject_unescapable_interpolation,
    failed_output,
)

PROJECT_ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(scope="module")
def mcp_server():
    """Load demo/mcp_server.py without requiring it to be an importable package."""
    spec = importlib.util.spec_from_file_location(
        "waf_mcp_server", PROJECT_ROOT / "demo" / "mcp_server.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ── 1. Configuration validation boundary ────────────────────────────────────


class TestValidationBoundary:
    def test_run_does_not_raise_on_invalid_config(self):
        result = run({"url": "https://example.com", "steps": []})

        assert result["status"] == "failed"
        assert result["aborted"] is True
        assert result["results"] == []

    def test_validation_error_is_structured_with_field_path(self):
        result = run(
            {
                "url": "https://example.com",
                "consent_statement": "t",
                "steps": [{"action": "click", "selector": "#a"}, {"action": "fill"}],
            }
        )

        entry = result["errors"][0]
        assert entry["code"] == "CONFIG_VALIDATION_ERROR"
        assert entry["field"] == "steps.1" or entry["field"].startswith("steps.1")
        assert entry["type"]
        assert "message" in entry

    def test_validation_error_reports_offending_step_index(self):
        result = run(
            {
                "url": "https://example.com",
                "consent_statement": "t",
                "steps": [{"action": "click", "selector": "#a"}],
                "options": {"step_delay_ms": 1},  # below the enforced minimum
            }
        )
        entry = result["errors"][0]
        assert entry["code"] == "CONFIG_VALIDATION_ERROR"
        assert entry["field"] == "options.step_delay_ms"

    def test_missing_top_level_field_is_reported_by_name(self):
        result = run({"url": "https://example.com", "steps": []})
        fields = {entry["field"] for entry in result["errors"]}
        assert "consent_statement" in fields

    def test_non_object_config_is_contained(self):
        result = run(["not", "an", "object"])  # type: ignore[arg-type]
        assert result["status"] == "failed"
        assert result["errors"][0]["code"] == "CONFIG_VALIDATION_ERROR"

    def test_error_message_is_not_a_pydantic_blob(self):
        result = run({"url": "x", "steps": []})
        message = result["errors"][0]["message"]
        assert "validation error for" not in message
        assert "pydantic.dev" not in message

    def test_low_level_model_still_raises(self):
        """WebAutoFormConfig stays the strict validator for direct callers."""
        from pydantic import ValidationError

        from web_auto_form.models import WebAutoFormConfig

        with pytest.raises(ValidationError):
            WebAutoFormConfig(url="x", steps=[])

    def test_run_from_path_contains_unparseable_json(self, tmp_path: Path):
        bad = tmp_path / "bad.json"
        bad.write_text("{not json", encoding="utf-8")

        result = run_from_path(str(bad))
        assert result["status"] == "failed"
        assert result["errors"][0]["code"] == "CONFIG_VALIDATION_ERROR"

    def test_run_from_path_contains_missing_file(self, tmp_path: Path):
        result = run_from_path(str(tmp_path / "nope.json"))
        assert result["status"] == "failed"
        assert result["errors"][0]["code"] == "CONFIG_VALIDATION_ERROR"


# ── 2. MCP / Agent tool handler ─────────────────────────────────────────────


class TestMcpHandlerContract:
    def test_invalid_config_through_mcp_handler_returns_structured_result(self, mcp_server):
        result = mcp_server.execute_config({"url": "https://example.com", "steps": []})

        assert result["status"] == "failed"
        assert result["errors"][0]["code"] == "CONFIG_VALIDATION_ERROR"
        json.dumps(result)  # must stay JSON-serialisable for TextContent

    def test_mcp_handler_never_raises(self, mcp_server, monkeypatch):
        def boom(config: dict) -> dict:
            raise RuntimeError("engine exploded")

        monkeypatch.setattr(mcp_server, "run", boom)
        result = mcp_server.execute_config({"url": "x", "steps": []})

        assert result["status"] == "failed"
        assert result["errors"][0]["code"] == "INTERNAL_ERROR"
        assert "RuntimeError" in result["errors"][0]["message"]

    def test_result_keys_match_the_runner_output(self, mcp_server):
        result = mcp_server.execute_config({"url": "https://example.com", "steps": []})
        assert set(result) == set(failed_output([]))


# ── 3. Action error contract completeness ───────────────────────────────────


class TestActionErrorContract:
    def test_scroll_failure_has_error_code(self):
        step = StepConfig(action="scroll", value="not-a-number")
        ctx = ActionContext(
            page=None,  # type: ignore[arg-type]
            step=step,
            options=OptionsConfig(),
            step_index=0,
        )
        result = run_scroll(ctx)

        assert result.status == "failed"
        assert result.error_code is not None
        assert isinstance(result.retryable, bool)

    def test_no_action_handler_is_missing_from_the_registry(self):
        """Every declared action must have a handler that reports failures."""
        assert set(ACTION_REGISTRY) == {
            "navigate",
            "fill",
            "select",
            "check",
            "click",
            "upload",
            "wait",
            "scroll",
            "extract",
            "press_key",
            "handle_dialog",
            "assert",
        }
        assert "if" not in ACTION_REGISTRY, "if is dispatcher-owned, not a handler"

    def test_navigate_failure_has_error_code(self):
        step = StepConfig(action="navigate", value="https://example.com")
        step.value = None  # unreachable via the schema; exercised directly
        ctx = ActionContext(
            page=None,  # type: ignore[arg-type]
            step=step,
            options=OptionsConfig(),
            step_index=0,
        )
        result = run_navigate(ctx)

        assert result.status == "failed"
        assert result.error_code is not None


# ── 4. Workflow budget enforcement ──────────────────────────────────────────


class TestWorkflowBudget:
    def _run(self, steps: list[dict], **options: Any) -> dict:
        opts: dict[str, Any] = {"headless": True, "step_delay_ms": 100}
        opts.update(options)
        return run(
            {
                "url": "https://example.com",
                "consent_statement": "budget test",
                "steps": steps,
                "options": opts,
            }
        )

    def test_wait_longer_than_budget_fails_fast(self, monkeypatch):
        """A wait must not outrun the budget by actually sleeping."""

        def no_sleep(seconds: float) -> None:
            raise AssertionError(f"should not sleep {seconds}s")

        monkeypatch.setattr(time, "sleep", no_sleep)

        step = StepConfig(action="wait", type="timeout", value="60000")
        ctx = ActionContext(
            page=None,  # type: ignore[arg-type]
            step=step,
            options=OptionsConfig(),
            step_index=0,
            remaining_budget_ms=1500,
        )
        result = run_wait(ctx)

        assert result.status == "failed"
        assert result.error_code == "TIMEOUT"
        assert "1500" in (result.error or "")

    def test_wait_within_budget_still_succeeds(self):
        step = StepConfig(action="wait", type="timeout", value="100")
        ctx = ActionContext(
            page=None,  # type: ignore[arg-type]
            step=step,
            options=OptionsConfig(),
            step_index=0,
            remaining_budget_ms=5000,
        )
        assert run_wait(ctx).status == "ok"

    def test_exhausted_budget_stops_the_workflow(self):
        """max_total_ms is the single budget knob; nothing may run past it."""
        started = time.monotonic()
        result = self._run(
            [{"action": "wait", "type": "timeout", "value": "5000"} for _ in range(5)],
            max_total_ms=1000,
            step_delay_ms=100,
        )
        elapsed = time.monotonic() - started

        assert result["status"] == "failed"
        assert result["aborted"] is True
        assert elapsed < 5.0, f"workflow outran its budget: {elapsed:.1f}s"
        assert result["errors"][-1]["code"] == "TIMEOUT"


# ── 5. Unescapable interpolation positions ──────────────────────────────────


class TestUnescapableInterpolation:
    def test_wait_function_rejects_template_js(self):
        """`value` is JavaScript in page context — a placeholder there is RCE."""
        result = run(
            {
                "url": "https://example.com",
                "consent_statement": "t",
                "data": {"x": "1"},
                "steps": [
                    {
                        "action": "wait",
                        "type": "function",
                        "value": "() => document.title === '{{x}}'",
                    }
                ],
            }
        )

        assert result["status"] == "failed"
        assert result["results"][0]["error_code"] == "TEMPLATE_ERROR"
        assert "JavaScript" in result["results"][0]["error"]

    def test_wait_function_without_placeholder_is_allowed(self):
        """The guard must key off the config, not off rendering."""
        step = StepConfig(action="wait", type="function", value="() => true")
        _reject_unescapable_interpolation(step)  # must not raise

    def test_matches_regex_rejects_templated_pattern(self):
        """A templated regex pattern is a ReDoS primitive, not just a bad match."""
        result = run(
            {
                "url": "https://example.com",
                "consent_statement": "t",
                "data": {"pat": "(a+)+$"},
                "steps": [
                    {
                        "action": "if",
                        "condition": {
                            "selector": "#x",
                            "operator": "matches_regex",
                            "expected_value": "{{pat}}",
                        },
                        "then": [{"action": "click", "selector": "#y"}],
                    }
                ],
            }
        )

        assert result["status"] == "failed"
        assert result["results"][0]["error_code"] == "TEMPLATE_ERROR"
        assert "regex" in result["results"][0]["error"]

    def test_matches_regex_with_literal_pattern_is_allowed(self):
        step = StepConfig(
            action="if",
            condition={
                "selector": "#x",
                "operator": "matches_regex",
                "expected_value": "^APP-[0-9]+$",
            },
            then=[{"action": "click", "selector": "#y"}],
        )
        _reject_unescapable_interpolation(step)  # must not raise

    def test_contains_with_template_is_allowed(self):
        """Only the regex position is unescapable; plain comparison is fine."""
        step = StepConfig(
            action="if",
            condition={
                "selector": "#x",
                "operator": "contains",
                "expected_value": "{{x}}",
            },
            then=[{"action": "click", "selector": "#y"}],
        )
        _reject_unescapable_interpolation(step)  # must not raise


# ── 6. Nothing is silently swallowed ────────────────────────────────────────


class TestTransparency:
    def test_failure_output_shape_is_stable(self):
        assert set(failed_output([])) == {
            "status",
            "consent_logged",
            "aborted",
            "steps_executed",
            "steps_skipped",
            "steps_failed",
            "results",
            "step_screenshots",
            "extracted",
            "final_screenshot",
            "debug_artifacts",
            "errors",
        }

    def test_step_outcome_enum_is_exported(self):
        assert {member.value for member in StepOutcome} == {"continue", "abort"}
