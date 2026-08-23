"""Entry point for the customer support agent.

Wires the MCP tool server (tools.py) and the hooks (hooks.py) into
ClaudeAgentOptions, and exposes a small `run()` helper that yields raw SDK
messages for one prompt. test_harness.py builds on `run()` to drive scenarios
and report the tool-call sequence.
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
        mcp_servers={"support": support_server},
        allowed_tools=ALL_TOOL_NAMES,
        hooks=HOOKS,
        system_prompt=SYSTEM_PROMPT,
    )


async def run(prompt: str) -> AsyncIterator[Message]:
    """Run a single prompt through the agent, yielding raw SDK messages."""

    options = build_options()
    async for message in query(prompt=prompt, options=options):
        yield message


async def _main() -> None:
    """Small smoke test: run one hardcoded prompt and print what happens."""

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
