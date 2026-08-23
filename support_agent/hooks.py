"""Hook registration for the support agent.

PreToolUse hooks run before a tool executes and can deny the call or rewrite
its input. PostToolUse hooks run after and can log the result or inject
context that steers the model's next turn. Returning `{}` leaves the
operation unchanged; returning `hookSpecificOutput` acts on it.

Signature: async def hook(input_data: dict, tool_use_id: str | None, context) -> dict
`input_data` always carries hook_event_name, tool_name, tool_input, session_id, cwd.
"""

from __future__ import annotations

import json
from typing import Any

from claude_agent_sdk import HookMatcher

from .backend import REFUND_APPROVAL_LIMIT

REFUND_TOOL = "mcp__support__process_refund"
LOOKUP_TOOLS_MATCHER = "mcp__support__get_customer|mcp__support__lookup_order"
ALL_SUPPORT_TOOLS_MATCHER = "^mcp__support__"


async def enforce_refund_policy(
    input_data: dict[str, Any], tool_use_id: str | None, context: Any
) -> dict[str, Any]:
    """Deny refunds over the approval limit before they reach the backend.

    Mirrors the limit check in backend.process_refund, but catching it here
    means the model gets a policy-shaped denial instead of spending a tool
    call to find out. process_refund still enforces its own limit as a
    backstop for any call that reaches it another way.
    """

    tool_input = input_data.get("tool_input", {})
    amount = tool_input.get("amount", 0)
    order_id = tool_input.get("order_id", "unknown")

    if amount > REFUND_APPROVAL_LIMIT:
        return {
            "hookSpecificOutput": {
                "hookEventName": input_data["hook_event_name"],
                "permissionDecision": "deny",
                "permissionDecisionReason": (
                    f"Refund of ${amount} on {order_id} exceeds the "
                    f"${REFUND_APPROVAL_LIMIT} limit an agent can approve. "
                    "Escalate to a human using escalate_to_human instead."
                ),
            }
        }

    return {}


async def normalize_lookup_input(
    input_data: dict[str, Any], tool_use_id: str | None, context: Any
) -> dict[str, Any]:
    """Trim and uppercase customer/order ids before they hit the backend."""

    tool_input = input_data.get("tool_input", {})
    cleaned = dict(tool_input)

    if "customer_id" in cleaned and isinstance(cleaned["customer_id"], str):
        cleaned["customer_id"] = cleaned["customer_id"].strip().upper()

    if "order_id" in cleaned and isinstance(cleaned["order_id"], str):
        cleaned["order_id"] = cleaned["order_id"].strip().upper()

    if cleaned == tool_input:
        return {}

    return {
        "hookSpecificOutput": {
            "hookEventName": input_data["hook_event_name"],
            "permissionDecision": "allow",
            "updatedInput": cleaned,
        }
    }


async def audit_tool_result(
    input_data: dict[str, Any], tool_use_id: str | None, context: Any
) -> dict[str, Any]:
    """Log every support-tool call and nudge escalation on dead-end errors.

    Structured errors travel back as a JSON string inside the tool result's
    text block (see errors.tool_error_result), so they're parsed back out
    here rather than being available as native fields.
    """

    tool_name = input_data.get("tool_name", "unknown")
    tool_input = input_data.get("tool_input", {})
    tool_result = input_data.get("tool_result", {})

    error_category = None
    is_retryable = None
    try:
        result_text = tool_result["content"][0]["text"]
        parsed = json.loads(result_text)
        error_category = parsed.get("errorCategory")
        is_retryable = parsed.get("isRetryable")
    except (KeyError, IndexError, TypeError, ValueError):
        pass  # Not a structured error payload -- nothing to extract.

    if error_category is not None:
        print(f"[AUDIT] {tool_name} args={tool_input} -> ERROR:{error_category}")
    else:
        print(f"[AUDIT] {tool_name} args={tool_input} -> ok")

    # Non-retryable permission/business errors are dead ends: point the model
    # at escalation instead of letting it retry or give up silently.
    if error_category in ("permission", "business") and is_retryable is False:
        return {
            "hookSpecificOutput": {
                "hookEventName": input_data["hook_event_name"],
                "additionalContext": (
                    f"The {tool_name} call failed with a non-retryable "
                    f"'{error_category}' error, so retrying will not help. "
                    "Call escalate_to_human with the customer and order details."
                ),
            }
        }

    return {}


HOOKS = {
    "PreToolUse": [
        HookMatcher(matcher=REFUND_TOOL, hooks=[enforce_refund_policy]),
        HookMatcher(matcher=LOOKUP_TOOLS_MATCHER, hooks=[normalize_lookup_input]),
    ],
    "PostToolUse": [
        HookMatcher(matcher=ALL_SUPPORT_TOOLS_MATCHER, hooks=[audit_tool_result]),
    ],
}
