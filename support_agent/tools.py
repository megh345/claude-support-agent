"""MCP tool definitions for the support agent.

Each tool is a thin wrapper: validate nothing here, call the mock backend,
and translate ToolError -> structured error content, or a plain dict ->
success content. The mock data and business rules live in backend.py.

`get_customer` and `lookup_order` are deliberately similar in shape (both
are "look up X by id" reads that return nested profile/order data), so their
descriptions are written to explicitly rule each other out and steer the
model toward the right one.
"""

from __future__ import annotations

from typing import Any

from claude_agent_sdk import ToolAnnotations, create_sdk_mcp_server, tool

from . import backend
from .errors import ToolError, tool_error_result, tool_success_result


@tool(
    "get_customer",
    (
        "Look up a CUSTOMER PROFILE by their customer id. "
        "Input: customer_id, a string shaped like 'CUST-1001'. "
        "Returns the customer's name, email, membership tier (standard/vip), "
        "member-since date, and a list of their recent order ids. "
        "Use this when you have a CUST- id and need to know WHO the customer "
        "is, verify their identity, or find which orders belong to them. "
        "Do NOT use this to look up order details (status, total, items) -- "
        "use lookup_order for that. If the id is not found you get a "
        "validation error; a frozen account returns a permission error."
    ),
    {"customer_id": str},
    annotations=ToolAnnotations(readOnlyHint=True),
)
async def get_customer(args: dict[str, Any]) -> dict[str, Any]:
    try:
        customer = backend.get_customer(args["customer_id"])
    except ToolError as e:
        return tool_error_result(e)
    return tool_success_result(customer)


@tool(
    "lookup_order",
    (
        "Look up a single ORDER's details by its order id. "
        "Input: order_id, a string shaped like 'ORD-1001'. "
        "Returns the order's status (e.g. delivered/processing), total amount, "
        "the items in it, whether it has already been refunded, and the id of "
        "the customer who placed it. "
        "Use this when you have an ORD- id and need details ABOUT AN ORDER -- "
        "for example before processing a refund, to check the total and "
        "whether it's already refunded. "
        "Do NOT use this to look up a person's profile or their list of "
        "orders -- use get_customer for that. If the id is not found you get "
        "a validation error; a backend timeout returns a transient "
        "(retryable) error."
    ),
    {"order_id": str},
    annotations=ToolAnnotations(readOnlyHint=True),
)
async def lookup_order(args: dict[str, Any]) -> dict[str, Any]:
    try:
        order = backend.lookup_order(args["order_id"])
    except ToolError as e:
        return tool_error_result(e)
    return tool_success_result(order)


@tool(
    "process_refund",
     (
        "Issue a refund against an order. THIS CHANGES DATA -- only call it "
        "once you have confirmed the order with lookup_order and know it is "
        "eligible. "
        "Inputs: order_id ('ORD-1001'), amount (a number, must be > 0 and not "
        "more than the order total), and reason (a short string). "
        "Returns a refund receipt on success. "
        "Fails with a business error if the order was already refunded, or if "
        "the amount is over the per-agent approval limit for a non-VIP "
        "customer -- in that case escalate_to_human instead of retrying."
    ),
    {"order_id": str, "amount": float, "reason": str},
)
async def process_refund(args: dict[str, Any]) -> dict[str, Any]:
    try:
        result = backend.process_refund(
            order_id=args["order_id"],
            amount=args["amount"],
            reason=args["reason"],
        )
    except ToolError as e:
        return tool_error_result(e)
    return tool_success_result(result)


@tool(
    "escalate_to_human",
    (
        "Hand the case off to a human support agent. Use this when the request "
        "is outside what you can resolve directly -- a refund over the "
        "approval limit, a frozen account, a policy gap, or an explicit "
        "customer request for a human. "
        "Inputs: reason (required, a short summary of why you're escalating), "
        "priority (required: 'low', 'normal', or 'high'), and optionally "
        "customer_id and order_id if they are known. "
        "Returns an open escalation ticket. Include enough detail in reason "
        "that the human can act without re-reading the whole conversation."
    ),

    {
        "type": "object",
        "properties": {
            "reason": {"type": "string"},
            "priority": {"type": "string", "enum": ["low", "normal", "high"]},
            "customer_id": {"type": ["string", "null"]},
            "order_id": {"type": ["string", "null"]},
        },
        "required": ["reason", "priority"],
    },
)
async def escalate_to_human(args: dict[str, Any]) -> dict[str, Any]:
    result = backend.escalate_to_human(
        reason=args["reason"],
        customer_id=args.get("customer_id"),
        order_id=args.get("order_id"),
        priority=args["priority"],
    )
    return tool_success_result(result)


support_server = create_sdk_mcp_server(
    name="support",
    version="1.0.0",
    tools=[get_customer, lookup_order, process_refund, escalate_to_human],
)

# Fully-qualified names, for allowed_tools / hook matchers.
ALL_TOOL_NAMES = [
    "mcp__support__get_customer",
    "mcp__support__lookup_order",
    "mcp__support__process_refund",
    "mcp__support__escalate_to_human",
]
