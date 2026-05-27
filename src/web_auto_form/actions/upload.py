"""Upload action: upload a file via a file input element."""

from __future__ import annotations

import base64
import logging
import os
import tempfile
from urllib.parse import urlparse
from urllib.request import urlopen

from .base import ActionContext, StepResult, timed

logger = logging.getLogger(__name__)


def _resolve_file(value: str, file_name: str | None) -> str:
    """Resolve value to a local file path, downloading remote URLs if needed."""
    if value.startswith(("http://", "https://")):
        resp = urlopen(value)
        data = resp.read()
        suffix = os.path.splitext(urlparse(value).path)[1] or ".bin"
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        tmp.write(data)
        tmp.close()
        return tmp.name

    if value.startswith("data:"):
        _, encoded = value.split(",", 1)
        data = base64.b64decode(encoded)
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".bin")
        tmp.write(data)
        tmp.close()
        return tmp.name

    if value.startswith("file://"):
        return value[len("file://"):]

    return value


@timed
def run_upload(ctx: ActionContext) -> StepResult:
    from ..selectors import find_element

    value = ctx.step.value
    if not value:
        return StepResult(
            step_index=ctx.step_index, action="upload", status="failed",
            error="upload requires a file path/URL in the value field",
        )

    loc = find_element(
        ctx.page, ctx.step.selector or "",
        ctx.step.selector_fallbacks, ctx.step.selector_type, ctx.step.timeout_ms,
    )
    if loc is None:
        return StepResult(
            step_index=ctx.step_index, action="upload", status="failed",
            error="file input element not found",
        )

    local_path = _resolve_file(value, ctx.step.file_name)

    is_temp = local_path != value and (
        value.startswith(("http://", "https://", "data:"))
    )

    try:
        file_payload = [{"name": ctx.step.file_name or os.path.basename(local_path), "buffer": open(local_path, "rb").read()}] if ctx.step.file_name else local_path
        loc.set_input_files(file_payload, timeout=ctx.step.timeout_ms)
    finally:
        if is_temp and os.path.exists(local_path):
            try:
                os.unlink(local_path)
            except OSError:
                pass

    return StepResult(step_index=ctx.step_index, action="upload", status="ok")
