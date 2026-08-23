"""Run a list of scenario prompts against the support agent and report, for
each one, which tools were called (in order) and the final response.

This is a diagnostic script, not an assertion-based test suite -- the point
is to *see* the tool sequence so you can compare it against what you
expected. Fill in NOTES.md with the actual vs. expected outcome per
scenario, especially for the misrouting and error-category probes.

Run with: python test_harness.py
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from claude_agent_sdk import AssistantMessage, ResultMessage, ToolUseBlock

from support_agent.agent import run

SCENARIOS: list[str] = [
    # Baseline: unambiguous single-tool call.
    "What's the status of order ORD-1001?",
    # Baseline: unambiguous single-tool call, the other lookup tool.
    "Can you pull up the account details for customer CUST-1001?",
    # Misrouting probe: get_customer and lookup_order both plausibly answer
    # this (get_customer via recent_order_ids, or lookup_order directly).
    # With placeholder descriptions this is expected to be ambiguous.
    "What did customer CUST-1001 order recently?",
    # Error category: transient (magic order id ORD-TIMEOUT).
    "Look up order ORD-TIMEOUT for me.",
    # Error category: validation (unknown id).
    "What's the status of order ORD-9999?",
    # Error category: permission (frozen account).
    "Pull up customer CUST-LOCKED's profile.",
    # Error category: business (order already refunded).
    "Please refund order ORD-1002 for $45, the customer changed their mind.",
    # Error category: business (amount exceeds agent's approval limit for a
    # non-VIP customer -- should ideally end in escalate_to_human).
    "Refund $400 on order ORD-1005 for customer CUST-1001, wrong item shipped.",
    # Multi-tool: expects a lookup followed by an escalation.
    "Customer CUST-1002 says order ORD-1003 arrived damaged and wants a manager to call them back.",
]


@dataclass
class ScenarioResult:
    prompt: str
    tool_calls: list[str] = field(default_factory=list)
    final_response: str | None = None


async def run_scenario(prompt: str) -> ScenarioResult:
    result = ScenarioResult(prompt=prompt)
    async for message in run(prompt):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, ToolUseBlock):
                    result.tool_calls.append(f"{block.name}({block.input})")
        elif isinstance(message, ResultMessage) and message.subtype == "success":
            result.final_response = message.result
    return result


def print_scenario_result(index: int, result: ScenarioResult) -> None:
    print(f"--- Scenario {index}: {result.prompt}")
    if result.tool_calls:
        print("  Tool sequence:")
        for i, call in enumerate(result.tool_calls, start=1):
            print(f"    {i}. {call}")
    else:
        print("  Tool sequence: (none)")
    print(f"  Final response: {result.final_response}")
    print()


async def main() -> None:
    for i, prompt in enumerate(SCENARIOS, start=1):
        result = await run_scenario(prompt)
        print_scenario_result(i, result)


if __name__ == "__main__":
    asyncio.run(main())
