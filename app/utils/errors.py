"""Structured error payloads for the IDJLM API.

Implements the A.2 taxonomy so callers get a consistent shape:

    {"error": "<short_code>", "detail": "<user-safe message>", "op": "<caller_op>"}

- `error`: machine-friendly short identifier (snake_case, never changing)
- `detail`: human-friendly message safe to show in the UI (never leaks stack traces)
- `op`: the caller's operation name (e.g. "review.approve"); optional

JSON shape MUST stay backwards compatible with the legacy
`{"error": "Operation failed"}` payloads that existed before A.2.

Service-layer code that previously raised bare `Exception` should
raise `AppError` (a subclass of Exception) with code/msg/op filled in;
the Flask error handler in app/__init__.py intercepts it.
"""
from __future__ import annotations

import logging
from typing import Optional

from flask import jsonify

logger = logging.getLogger(__name__)


# Short error codes. Stable identifier — UI/front-end may match on this.
class Err:
    UNKNOWN = "unknown"               # default fallback
    FILE_NOT_FOUND = "file_not_found"
    INVALID_BODY = "invalid_body"
    INVALID_PATH = "invalid_path"
    MISSING_PARAM = "missing_param"
    PERMISSION = "permission_denied"
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    IO_ERROR = "io_error"
    PARSE_ERROR = "parse_error"
    INVALID_STATE = "invalid_state"
    UPSTREAM = "upstream_error"        # third-party API/AI failure
    TIMEOUT = "timeout"
    NOT_IMPLEMENTED = "not_implemented"


class AppError(Exception):
    """Domain-level error with structured payload.

    Use as:
        raise AppError(Err.NOT_FOUND, f"Track not found: {path}", op="review.approve")

    The Flask error handler in app/__init__.py catches AppError and converts it
    to a structured JSON response with status_code.
    """

    def __init__(
        self,
        code: str,
        message: str,
        op: Optional[str] = None,
        status_code: int = 400,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.op = op
        self.status_code = int(status_code)


def make_error_payload(
    code: str, message: str, op: Optional[str] = None
) -> dict:
    """Build a structured error payload (for return-from-route, no raise)."""
    payload: dict = {"error": code, "detail": message}
    if op:
        payload["op"] = op
    return payload


def error_response(
    code: str,
    message: str,
    op: Optional[str] = None,
    status_code: int = 400,
):
    """Return a Flask JSON response (400 by default) with structured error."""
    payload = make_error_payload(code, message, op)
    return jsonify(payload), status_code


def log_app_error(err: AppError, *, route: Optional[str] = None) -> None:
    """Server-side structured log. Safe to call from the Flask handler."""
    logger.warning(
        "AppError code=%s op=%s route=%s message=%s",
        err.code,
        err.op,
        route,
        err.message,
        exc_info=False,
    )


def log_unexpected_error(
    exc: Exception, *, route: Optional[str] = None, op: Optional[str] = None
) -> None:
    """Server-side unexpected-exception log."""
    logger.error(
        "Unhandled exception route=%s op=%s type=%s message=%s",
        route,
        op,
        type(exc).__name__,
        str(exc),
        exc_info=True,
    )
