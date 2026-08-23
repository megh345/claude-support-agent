"""Structured error responses for support agent tools.

Every mock backend failure gets normalized into one of four categories so the
agent (and eventually a human reviewing logs) can tell "try again" apart from
"stop and ask a person."
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Literal

ErrorCategory = Literal["transient", "validation", "permission", "business"]

# Whether a given category is retryable by default. A tool can still override
# this per-error (e.g. a validation error is normally not retryable, but that's
# a category default, not a law of physics).
DEFAULT_RETRYABLE: dict[ErrorCategory, bool] = {
    "transient": True,
    "validation": False,
    "permission": False,
    "business": False,
}


@dataclass
class ToolError(Exception):
    """A structured error a mock backend can raise."""

    category: ErrorCategory
    message: str
    is_retryable: bool | None = None
    details: dict[str, Any] | None = None

    def __post_init__(self) -> None:
        Exception.__init__(self, self.message)

    def to_payload(self) -> dict[str, Any]:
        return {
            "errorCategory": self.category,
            "isRetryable": (
                self.is_retryable
                if self.is_retryable is not None
                else DEFAULT_RETRYABLE[self.category]
            ),
            "message": self.message,
            "details": self.details or {},
        }


def tool_error_result(error: ToolError) -> dict[str, Any]:
    """Shape a ToolError into the dict a Python @tool handler must return.

    The Python SDK only forwards `content` and `is_error` from a handler's
    return dict (no `structuredContent` support), so the structured error
    payload travels as JSON text inside the single content block.
    """

    return {
        "content": [{"type": "text", "text": json.dumps(error.to_payload())}],
        "is_error": True,
    }


def tool_success_result(payload: dict[str, Any]) -> dict[str, Any]:
    """Shape a successful backend payload into a tool handler return dict."""

    return {"content": [{"type": "text", "text": json.dumps(payload)}]}
