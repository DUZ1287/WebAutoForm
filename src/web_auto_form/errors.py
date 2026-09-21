"""Structured error model: error codes, exception classification, retryability.

Two separate concepts live here and must not be conflated:

* ``retryable`` is a property of the *error* — is retrying this class of failure
  ever sensible?
* whether a retry actually happens is a *failure policy* decision made by the
  Runner (see ``runner._should_retry``), gated on ``retry_on`` and
  ``max_retries``.

Playwright raises a handful of exception types with free-form messages, so
classification is keyed on the exception *type* first. Message inspection is
used only to refine the code inside a type that genuinely covers several
conditions (notably ``TimeoutError``) — never as the primary signal.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from playwright.sync_api import Error as PwError
from playwright.sync_api import TimeoutError as PwTimeout
from pydantic import ValidationError

from .templates import TemplateSecurityError


class ErrorCode(str, Enum):
    """Machine-readable failure classification attached to every failed step."""

    ELEMENT_NOT_FOUND = "ELEMENT_NOT_FOUND"
    ELEMENT_NOT_VISIBLE = "ELEMENT_NOT_VISIBLE"
    ELEMENT_NOT_INTERACTABLE = "ELEMENT_NOT_INTERACTABLE"
    TIMEOUT = "TIMEOUT"
    NAVIGATION_FAILED = "NAVIGATION_FAILED"
    NETWORK_ERROR = "NETWORK_ERROR"
    INVALID_SELECTOR = "INVALID_SELECTOR"
    ASSERTION_FAILED = "ASSERTION_FAILED"
    FILE_UPLOAD_FAILED = "FILE_UPLOAD_FAILED"
    TEMPLATE_ERROR = "TEMPLATE_ERROR"
    CONFIG_VALIDATION_ERROR = "CONFIG_VALIDATION_ERROR"
    INTERNAL_ERROR = "INTERNAL_ERROR"
    UNKNOWN = "UNKNOWN"


#: Codes whose failures may be transient, so a retry can plausibly succeed.
#:
#: ELEMENT_NOT_FOUND is deliberately absent: ``find_element`` already spends the
#: step's full timeout searching the fallback chain, so re-running the identical
#: lookup is almost always wasted time. The "element exists but is in a
#: transient state" codes are included because visibility/stability usually
#: settles on its own.
RETRYABLE_CODES: frozenset[ErrorCode] = frozenset(
    {
        ErrorCode.NETWORK_ERROR,
        ErrorCode.NAVIGATION_FAILED,
        ErrorCode.TIMEOUT,
        ErrorCode.ELEMENT_NOT_VISIBLE,
        ErrorCode.ELEMENT_NOT_INTERACTABLE,
    }
)

# Selector-engine failures. Playwright rejects these before any network or DOM
# interaction, so they are permanent by construction. The marker list covers the
# messages both Playwright's own parser and Chromium emit in practice; a
# malformed selector must never degrade to UNKNOWN, or the Agent repair loop gets
# no signal that the config itself is wrong.
_INVALID_SELECTOR_MARKERS = (
    "is not a valid selector",
    "invalidselectorerror",
    "unknown engine",
    "unexpected token",
    "unsupported token",
    "while parsing css selector",
    "while parsing selector",
    "failed to execute 'queryselector",
)

_NETWORK_MARKERS = (
    "econnreset",
    "econnrefused",
    "connection refused",
    "socket hang up",
)

# Checked before _NETWORK_MARKERS: net::ERR_ABORTED means the request was
# cancelled by a navigation, not that the transport failed.
_NAVIGATION_MARKERS = (
    "net::err_aborted",
    "frame was detached",
    "execution context was destroyed",
)

# Chromium's generic transport-failure prefix (net::ERR_CONNECTION_REFUSED,
# net::ERR_NAME_NOT_RESOLVED, net::ERR_UNSAFE_PORT, ...). Matched as a family so
# new ERR_ codes do not silently fall through to UNKNOWN.
_NET_PREFIX = "net::err"

_INTERACTABLE_MARKERS = (
    "intercepts pointer events",
    "element is outside of the viewport",
    "element is not stable",
    "element is not enabled",
)

_NOT_VISIBLE_MARKERS = ("element is not visible", "not visible")

_CLOSED_MARKERS = ("browser has been closed", "target page, context", "target closed")

_UPLOAD_ACTIONS = frozenset({"upload"})
_NAVIGATION_ACTIONS = frozenset({"navigate"})


@dataclass(frozen=True)
class ErrorInfo:
    """A classified failure: a stable code plus a human-readable message."""

    code: ErrorCode
    message: str

    @property
    def retryable(self) -> bool:
        """Whether this class of error is ever worth retrying."""
        return self.code in RETRYABLE_CODES


def _summarize(exc: BaseException, full: str) -> str:
    """Reduce an exception to a single readable line (Playwright logs are huge)."""
    first = full.splitlines()[0].strip() if full else ""
    if not first:
        first = type(exc).__name__
    if isinstance(exc, PwError):
        # Playwright's first line already names the failure clearly.
        return first
    return f"{type(exc).__name__}: {first}"


def classify_exception(exc: BaseException, action: str | None = None) -> ErrorInfo:
    """Classify an exception raised while executing *action*.

    Args:
        exc: The exception escaping an action handler.
        action: The DSL action name the exception came from, used to
            disambiguate otherwise identical Playwright messages.

    Returns:
        An :class:`ErrorInfo`. Never raises.
    """
    full = str(exc).strip()
    text = full.lower()
    summary = _summarize(exc, full)

    if isinstance(exc, TemplateSecurityError):
        # Raised before any browser interaction, so it is a config defect rather
        # than a page condition. Checked first because it subclasses ValueError.
        return ErrorInfo(ErrorCode.TEMPLATE_ERROR, summary)

    if isinstance(exc, PwError):
        # TimeoutError subclasses Error and covers many conditions, so the
        # shared markers are checked first and the timeout branch only refines
        # what is left. Playwright's timeout message embeds its call log, which
        # is where these markers come from.
        if any(marker in text for marker in _INVALID_SELECTOR_MARKERS):
            return ErrorInfo(ErrorCode.INVALID_SELECTOR, summary)
        if any(marker in text for marker in _CLOSED_MARKERS):
            return ErrorInfo(ErrorCode.INTERNAL_ERROR, summary)
        if any(marker in text for marker in _INTERACTABLE_MARKERS):
            return ErrorInfo(ErrorCode.ELEMENT_NOT_INTERACTABLE, summary)
        if any(marker in text for marker in _NAVIGATION_MARKERS):
            return ErrorInfo(ErrorCode.NAVIGATION_FAILED, summary)
        if _NET_PREFIX in text or any(marker in text for marker in _NETWORK_MARKERS):
            return ErrorInfo(ErrorCode.NETWORK_ERROR, summary)
        if any(marker in text for marker in _NOT_VISIBLE_MARKERS):
            return ErrorInfo(ErrorCode.ELEMENT_NOT_VISIBLE, summary)

        if isinstance(exc, PwTimeout):
            if action in _NAVIGATION_ACTIONS or "waiting for navigation" in text:
                return ErrorInfo(ErrorCode.NAVIGATION_FAILED, summary)
            if "waiting for load state" in text:
                return ErrorInfo(ErrorCode.NAVIGATION_FAILED, summary)
            if "locator resolved to" in text:
                # Found, but never became visible/enabled/stable in time.
                return ErrorInfo(ErrorCode.ELEMENT_NOT_VISIBLE, summary)
            if "locator" in text or "waiting for" in text:
                return ErrorInfo(ErrorCode.ELEMENT_NOT_FOUND, summary)
            return ErrorInfo(ErrorCode.TIMEOUT, summary)

        if action in _UPLOAD_ACTIONS:
            # Playwright has no upload-specific error type; anything it raises
            # from set_input_files (missing file, unsupported MIME) is a failed
            # upload as far as the workflow is concerned.
            return ErrorInfo(ErrorCode.FILE_UPLOAD_FAILED, summary)
        return ErrorInfo(ErrorCode.UNKNOWN, summary)

    if isinstance(exc, OSError):
        if action in _UPLOAD_ACTIONS:
            return ErrorInfo(ErrorCode.FILE_UPLOAD_FAILED, summary)
        return ErrorInfo(ErrorCode.UNKNOWN, summary)

    if isinstance(exc, Exception):
        # Anything else is a bug on our side, not a page condition.
        return ErrorInfo(ErrorCode.INTERNAL_ERROR, summary)

    return ErrorInfo(ErrorCode.UNKNOWN, summary)


# ── Structured error entries for the output `errors` array ─────────────────


def error_entry(code: ErrorCode, message: str, **details: Any) -> dict[str, Any]:
    """Build one machine-consumable entry for the output ``errors`` array.

    Keys with a ``None`` value are dropped so the shape stays stable and small.
    """
    entry: dict[str, Any] = {"code": code.value, "message": message}
    entry.update({key: value for key, value in details.items() if value is not None})
    return entry


def validation_entries(exc: ValidationError) -> list[dict[str, Any]]:
    """Flatten a Pydantic ``ValidationError`` into structured, bounded entries.

    A raw ``str(exc)`` is a multi-line blob with a docs URL — unusable for an
    Agent that needs to know *which* field to fix. The dotted ``field`` path
    (e.g. ``steps.2.selector``) is the actionable part.
    """
    entries: list[dict[str, Any]] = []
    for error in exc.errors():
        location = error.get("loc") or ()
        field = ".".join(str(part) for part in location)
        entry = error_entry(
            ErrorCode.CONFIG_VALIDATION_ERROR,
            str(error.get("msg", "invalid value")),
            field=field or None,
            type=error.get("type"),
        )
        # Surface the offending step index so a caller can index straight into
        # `steps` without re-parsing the field path.
        if (
            len(location) >= 2
            and location[0] in ("steps", "locator_fallbacks")
            and (isinstance(location[1], int))
        ):
            entry.setdefault("step", location[1])
        entries.append(entry)
    return entries
