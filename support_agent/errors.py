"""Structured error responses for support agent tools.

Normalize backend failures into four categories. This helps the agent decide
whether it should retry, fix the input, stop because access is blocked, or
escalate the issue to a human.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Literal

ErrorCategory = Literal["transient", "validation", "permission", "business"]

# Default retry behavior for each error category. A tool can override this for
# a specific error when needed.
DEFAULT_RETRYABLE: dict[ErrorCategory, bool] = {
    "transient": True,
    "validation": False,
    "permission": False,
    "business": False,
}


@dataclass
class ToolError(Exception):
    """Structured exception raised by the mock backend."""

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
    """Convert a ToolError into the dict returned by a Python @tool handler.

    The Python SDK forwards `content` and `is_error` from the handler return
    value. Since structuredContent is not available here, I send the structured
    error payload as JSON text inside one content block.
    """

    return {
        "content": [{"type": "text", "text": json.dumps(error.to_payload())}],
        "is_error": True,
    }


def tool_success_result(payload: dict[str, Any]) -> dict[str, Any]:
    """Convert a successful backend payload into a tool result dict."""

    return {"content": [{"type": "text", "text": json.dumps(payload)}]}
