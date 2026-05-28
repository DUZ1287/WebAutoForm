"""Pydantic models for the web_auto_form configuration schema."""

from __future__ import annotations

import re
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field, model_validator


class ConditionConfig(BaseModel):
    """Condition for the 'if' action."""

    selector: str
    attribute: str = "textContent"
    state: Optional[Literal["exist", "not_exist", "visible", "hidden", "checked"]] = None
    operator: Optional[Literal["eq", "ne", "contains", "matches_regex"]] = None
    expected_value: Optional[str] = None


class StepConfig(BaseModel):
    """A single atomic browser operation."""

    action: Literal[
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
        "if",
        "assert",
    ]
    selector: Optional[str] = None
    selector_type: Optional[Literal["css", "xpath", "id", "name", "placeholder", "data-testid"]] = (
        None
    )
    selector_fallbacks: list[str] = Field(default_factory=list)
    value: Optional[str] = None
    file_name: Optional[str] = None
    timeout_ms: int = Field(default=5000, ge=0, le=60000)
    type: Literal["element", "navigation", "timeout", "function"] = "element"
    state: Literal["exist", "not_exist", "visible", "hidden", "enabled", "disabled", "checked"] = (
        "exist"
    )
    operator: Optional[Literal["eq", "ne", "contains", "matches_regex"]] = None
    expected_value: Optional[str] = None
    on_fail: Literal["abort", "continue", "retry"] = "abort"
    max_retries: Optional[int] = Field(default=None, ge=1, le=5)
    retry_on: Optional[list[str]] = None
    optional: bool = False
    on_skip: Literal["log", "abort", "set_default"] = "log"
    screenshot: bool = False
    description: Optional[str] = None
    condition: Optional[ConditionConfig] = None
    then_steps: list[StepConfig] = Field(default_factory=list, alias="then")
    else_steps: list[StepConfig] = Field(default_factory=list, alias="else")

    model_config = {"populate_by_name": True}

    @model_validator(mode="after")
    def _validate_step(self) -> StepConfig:
        # wait type=timeout requires numeric value
        if self.action == "wait" and self.type == "timeout":
            if not self.value or not re.match(r"^\d+$", self.value):
                raise ValueError("wait type=timeout requires value as a numeric string (ms)")
        # wait type=function requires value
        if self.action == "wait" and self.type == "function":
            if not self.value:
                raise ValueError("wait type=function requires a non-empty value (JS expression)")
        # navigate requires value
        if self.action == "navigate" and not self.value:
            raise ValueError("navigate requires a value (URL)")
        # fill/select/check/click/upload/extract/assert require selector
        if self.action in ("fill", "select", "check", "click", "upload", "extract", "assert"):
            if not self.selector:
                raise ValueError(f"{self.action} requires a selector")
        # if requires condition and then
        if self.action == "if":
            if not self.condition:
                raise ValueError("if action requires a condition")
            if not self.then_steps:
                raise ValueError("if action requires 'then' steps")
        return self


class ExtractFieldConfig(BaseModel):
    """A single field to extract from the final page."""

    name: str
    selector: str
    attribute: str = "text"
    redact: Optional[bool] = None


class ExtractSchemaConfig(BaseModel):
    """Schema for structured extraction after all steps complete."""

    fields: list[ExtractFieldConfig] = Field(default_factory=list)
    screenshot: bool = False


class OptionsConfig(BaseModel):
    """Global execution options."""

    headless: bool = True
    viewport_width: int = 1280
    viewport_height: int = 800
    user_agent: Optional[str] = None
    locale: str = "en-US"
    step_delay_ms: int = Field(default=500, ge=100, le=10000)
    max_retries: int = Field(default=1, ge=1, le=5)
    retry_on: list[str] = Field(default_factory=lambda: ["NETWORK_ERROR"])
    sandbox: bool = True
    redact_pii: bool = True
    debug: bool = False
    debug_output_path: str = "./web_auto_form_debug_<timestamp>/"
    keep_open: bool = False
    upload_enforce_extension: bool = False
    diagnose_on_failure: bool = True


class WebAutoFormConfig(BaseModel):
    """Top-level configuration for a web_auto_form run."""

    url: str
    consent_statement: str
    data: dict[str, Any] = Field(default_factory=dict)
    steps: list[StepConfig] = Field(min_length=1, max_length=50)
    extract_schema: ExtractSchemaConfig = Field(default_factory=ExtractSchemaConfig)
    options: OptionsConfig = Field(default_factory=OptionsConfig)
