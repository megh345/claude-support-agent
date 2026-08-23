"""Mock backend: fake customer/order data and the "business logic" that the
MCP tools in tools.py wrap. Kept separate from tools.py so the tool layer
(schemas, descriptions, MCP plumbing) doesn't get tangled up with fake data.

Magic IDs used to deliberately trigger each error category (see errors.py):

    customer_id "CUST-404"   -> validation  (customer not found)
    customer_id "CUST-LOCKED"-> permission   (account frozen, needs elevated access)
    order_id    "ORD-404"    -> validation  (order not found)
    order_id    "ORD-TIMEOUT"-> transient   (simulated backend timeout)
    refund on   "ORD-1002"   -> business    (already refunded)
    refund on   "ORD-1005" for amount > REFUND_APPROVAL_LIMIT -> business
        (owned by a non-VIP customer; exceeds what an agent can approve
        without escalation)
"""

from __future__ import annotations

from typing import Any

from .errors import ToolError

REFUND_APPROVAL_LIMIT = 250.00

# --- Fake data -------------------------------------------------------------

_CUSTOMERS: dict[str, dict[str, Any]] = {
    "CUST-1001": {
        "customer_id": "CUST-1001",
        "name": "Priya Raman",
        "email": "priya.raman@example.com",
        "tier": "standard",
        "member_since": "2022-03-14",
        "recent_order_ids": ["ORD-1001", "ORD-1002", "ORD-1005"],
    },
    "CUST-1002": {
        "customer_id": "CUST-1002",
        "name": "Marcus Webb",
        "email": "marcus.webb@example.com",
        "tier": "vip",
        "member_since": "2019-11-02",
        "recent_order_ids": ["ORD-1003"],
    },
    "CUST-LOCKED": {
        "customer_id": "CUST-LOCKED",
        "name": "Dana Okafor",
        "email": "dana.okafor@example.com",
        "tier": "standard",
        "member_since": "2021-07-30",
        "recent_order_ids": ["ORD-1004"],
        "account_frozen": True,
    },
}

_ORDERS: dict[str, dict[str, Any]] = {
    "ORD-1001": {
        "order_id": "ORD-1001",
        "customer_id": "CUST-1001",
        "status": "delivered",
        "total": 89.99,
        "items": [{"sku": "SKU-4471", "name": "Wireless Mouse", "qty": 1}],
        "refunded": False,
    },
    "ORD-1002": {
        "order_id": "ORD-1002",
        "customer_id": "CUST-1001",
        "status": "delivered",
        "total": 45.00,
        "items": [{"sku": "SKU-2210", "name": "USB-C Cable", "qty": 3}],
        "refunded": True,
    },
    "ORD-1003": {
        "order_id": "ORD-1003",
        "customer_id": "CUST-1002",
        "status": "delivered",
        "total": 1240.00,
        "items": [{"sku": "SKU-9981", "name": "Mechanical Keyboard", "qty": 2}],
        "refunded": False,
    },
    "ORD-1005": {
        "order_id": "ORD-1005",
        "customer_id": "CUST-1001",
        "status": "delivered",
        "total": 600.00,
        "items": [{"sku": "SKU-7765", "name": "4K Monitor", "qty": 1}],
        "refunded": False,
    },
    "ORD-1004": {
        "order_id": "ORD-1004",
        "customer_id": "CUST-LOCKED",
        "status": "processing",
        "total": 60.00,
        "items": [{"sku": "SKU-3312", "name": "Laptop Stand", "qty": 1}],
        "refunded": False,
    },
}

_escalations: list[dict[str, Any]] = []


# --- Backend operations ------------------------------------------------
# Each returns either a plain dict (success payload) or raises ToolError.


def get_customer(customer_id: str) -> dict[str, Any]:
    if customer_id == "CUST-404":
        raise ToolError("validation", f"No customer found with id '{customer_id}'.")

    customer = _CUSTOMERS.get(customer_id)
    if customer is None:
        raise ToolError("validation", f"No customer found with id '{customer_id}'.")

    if customer.get("account_frozen"):
        raise ToolError(
            "permission",
            f"Customer '{customer_id}' account is frozen. Agent-level access "
            "is not sufficient to view this profile.",
            details={"required_role": "trust_and_safety"},
        )

    return {k: v for k, v in customer.items() if k != "account_frozen"}


def lookup_order(order_id: str) -> dict[str, Any]:
    if order_id == "ORD-TIMEOUT":
        raise ToolError(
            "transient",
            "Order service timed out while looking up the order. Try again.",
            details={"timeout_ms": 5000},
        )

    if order_id == "ORD-404":
        raise ToolError("validation", f"No order found with id '{order_id}'.")

    order = _ORDERS.get(order_id)
    if order is None:
        raise ToolError("validation", f"No order found with id '{order_id}'.")

    return dict(order)


def process_refund(order_id: str, amount: float, reason: str) -> dict[str, Any]:
    if order_id == "ORD-TIMEOUT":
        raise ToolError(
            "transient",
            "Payment service timed out while processing the refund. Try again.",
            details={"timeout_ms": 8000},
        )

    order = _ORDERS.get(order_id)
    if order is None:
        raise ToolError("validation", f"No order found with id '{order_id}'.")

    if amount <= 0:
        raise ToolError("validation", "Refund amount must be greater than zero.")

    if amount > order["total"]:
        raise ToolError(
            "validation",
            f"Refund amount {amount} exceeds order total {order['total']}.",
        )

    if order["refunded"]:
        raise ToolError(
            "business",
            f"Order '{order_id}' has already been refunded.",
            details={"order_id": order_id},
        )

    customer = _CUSTOMERS.get(order["customer_id"], {})
    if amount > REFUND_APPROVAL_LIMIT and customer.get("tier") != "vip":
        raise ToolError(
            "business",
            f"Refund of {amount} exceeds the {REFUND_APPROVAL_LIMIT} limit an "
            "agent can approve for a non-VIP customer. Escalate to a human "
            "for approval.",
            details={"limit": REFUND_APPROVAL_LIMIT, "customer_tier": customer.get("tier", "unknown")},
        )

    order["refunded"] = True
    return {
        "order_id": order_id,
        "refund_amount": amount,
        "reason": reason,
        "status": "refund_issued",
    }


def escalate_to_human(reason: str, customer_id: str | None, order_id: str | None, priority: str) -> dict[str, Any]:
    ticket_id = f"ESC-{1000 + len(_escalations) + 1}"
    ticket = {
        "ticket_id": ticket_id,
        "reason": reason,
        "customer_id": customer_id,
        "order_id": order_id,
        "priority": priority,
        "status": "open",
    }
    _escalations.append(ticket)
    return ticket
