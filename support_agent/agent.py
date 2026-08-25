"""Main entry point for the customer support agent.

Connect the MCP tool server from tools.py and the hooks from hooks.py to
ClaudeAgentOptions. The `run()` helper sends one prompt to the agent and yields
the raw SDK messages. test_harness.py uses this helper to run scenarios and
print the tool-call sequence.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    Message,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
    query,
)

from .hooks import HOOKS
from .tools import ALL_TOOL_NAMES, support_server

SYSTEM_PROMPT = (
    "You are a customer support agent for an online retailer. Use the "
    "available tools to look up customers and orders, process refunds, and "
    "escalate to a human when a request is outside what you can resolve "
    "directly. Don't guess at customer or order data -- always look it up."
)


def build_options() -> ClaudeAgentOptions:
    return ClaudeAgentOptions(
        model="claude-sonnet-4-6",
        mcp_servers={"support": support_server},
        allowed_tools=ALL_TOOL_NAMES,
        hooks=HOOKS,
        system_prompt=SYSTEM_PROMPT,
    )


async def run(prompt: str) -> AsyncIterator[Message]:
    """Run one prompt through the agent and yield each SDK message."""

    options = build_options()
    async for message in query(prompt=prompt, options=options):
        yield message


async def _main() -> None:
    """Run a small smoke test with one hardcoded prompt."""

    async for message in run("What's the status of order ORD-1001?"):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, ToolUseBlock):
                    print(f"[tool call] {block.name}({block.input})")
                elif isinstance(block, TextBlock):
                    print(f"[assistant] {block.text}")
        elif isinstance(message, ResultMessage) and message.subtype == "success":
            print(f"\n[final] {message.result}")


if __name__ == "__main__":
    asyncio.run(_main())
