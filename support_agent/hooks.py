"""Hook registration for the support agent.

Use PreToolUse hooks to inspect a tool call before it runs. These hooks can
deny the call or update the input. Use PostToolUse hooks after a tool returns
so that I can log the result or add context for the model's next step.

Returning `{}` means the hook does not change anything. Returning
`hookSpecificOutput` tells the SDK to apply the hook result.

Hook signature:
async def hook(input_data: dict, tool_use_id: str | None, context) -> dict

`input_data` includes hook_event_name, tool_name, tool_input, session_id, and cwd.
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
    """Deny refunds above the agent approval limit before backend execution.

    This matches the limit check in backend.process_refund. Keep the backend
    check as the final protection, but this hook gives the model a clear policy
    denial earlier in the flow.
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
    """Normalize customer and order ids before the backend receives them."""

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
    """Log support tool results and guide the model on non-retryable errors.

    Structured errors come back as JSON text in the tool result content block.
    Parse that text here so the hook can read the error category and retry
    flag.
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
        pass  # This was not a structured error payload, so there is nothing to extract.

    if error_category is not None:
        print(f"[AUDIT] {tool_name} args={tool_input} -> ERROR:{error_category}")
    else:
        print(f"[AUDIT] {tool_name} args={tool_input} -> ok")

    # Permission and business errors are not retryable, so the next step should
    # be escalation instead of another attempt.
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
