# Customer Support Resolution Agent

A customer-support agent built with the **Claude Agent SDK**. It resolves common support requests — order lookups, customer lookups, and refunds — autonomously, and escalates to a human when a request falls outside what it's allowed to handle.

I built this while preparing for the **Claude Certified Architect – Foundations** certification, as a hands-on way to internalize the SDK's core patterns: the agentic loop, tool design, structured error handling, and deterministic policy enforcement via hooks.

---

## Architecture

```text
User prompt
    │
    ▼
agent.py ── query() runs the agentic loop
    │
    ├─ hooks.py    guards around each tool call (block / normalize / audit)
    │
    ├─ tools.py    thin MCP wrappers around the backend functions
    │
    ├─ backend.py  the actual work + business rules (raises ToolError on failure)
    │
    └─ errors.py   ToolError + the success/error response envelopes
```

Each layer has a single responsibility:

* **`backend.py`** — mock customer/order data and the business logic. Raises a structured `ToolError` when something is wrong (not found, frozen account, already refunded, over the approval limit, etc.).
* **`errors.py`** — defines `ToolError` and its four categories, and shapes results into the content/`is_error` envelope the agent expects.
* **`tools.py`** — wraps each backend function as an MCP tool, translating a raised `ToolError` into a structured error response and a plain result into a success response. Tool descriptions are written to disambiguate the two similarly-shaped lookup tools.
* **`hooks.py`** — three lifecycle hooks: enforce the refund policy, normalize lookup identifiers, and audit results (nudging escalation on dead-end errors).
* **`agent.py`** — assembles tools, hooks, and the system prompt into `ClaudeAgentOptions`, and exposes a `run()` helper that streams SDK messages.
* **`test_harness.py`** — drives the agent through a battery of scenarios and reports the tool sequence and final response for each.

---

## Tools

| Tool                | Purpose                                  | Read-only        |
| ------------------- | ---------------------------------------- | ---------------- |
| `get_customer`      | Look up a customer profile by `CUST-` id | ✅                |
| `lookup_order`      | Look up an order's details by `ORD-` id  | ✅                |
| `process_refund`    | Issue a refund against an order          | ❌ (changes data) |
| `escalate_to_human` | Hand the case off to a human agent       | ❌                |

---

## Error categories

Every backend failure is normalized into one of four categories so the agent can react appropriately:

| Category     | Meaning                                               | Retryable |
| ------------ | ----------------------------------------------------- | --------- |
| `transient`  | Temporary glitch (e.g. a timeout)                     | ✅ Yes     |
| `validation` | Bad input (e.g. unknown id)                           | ❌ No      |
| `permission` | Not allowed (e.g. frozen account)                     | ❌ No      |
| `business`   | Blocked by policy (e.g. already refunded, over limit) | ❌ No      |

---

## Setup

Requires Python 3.10+ and an Anthropic API key.

```bash
# 1. Clone
git clone https://github.com/<your-username>/customer-support-agent.git
cd customer-support-agent

# 2. Create and activate a virtual environment
python -m venv venv
source venv/bin/activate          # macOS/Linux
# venv\Scripts\activate           # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Provide your API key
export ANTHROPIC_API_KEY="your-key-here"
```
---

## Running it

**Single-prompt demo** (prints the tool calls and final answer for one request):

```bash
python -m support_agent.agent
```

> Note: `agent.py` uses package-relative imports, so it must be run as a module (`-m`) from the project root, not as `python support_agent/agent.py`.

**Full scenario harness** (runs a suite of probes and reports each result):

```bash
python test_harness.py
```
---

## Scenarios covered by the harness

The harness exercises the happy path, every error category, tool-routing between the two lookup tools, and a multi-tool flow ending in escalation:

* Baseline single-tool lookups (order and customer)
* Tool-routing probe between `get_customer` and `lookup_order`
* `transient` error (`ORD-TIMEOUT`)
* `validation` error (unknown id)
* `permission` error (frozen account, `CUST-LOCKED`)
* `business` error (order already refunded)
* Over-limit refund that should be blocked and escalated
* A damaged-order request that should end in a human handoff

Expected vs. actual outcomes for each scenario are tracked in `NOTES.md`.

---

## Notes on scope

The backend is intentionally a **mock** — in-memory dictionaries with a set of "magic" ids that deliberately trigger each error category, so the agent's behavior can be observed end-to-end without a real database or payment system.

The focus is the agent architecture, not the backend implementation.

---

## About this project

This is a learning project, built with AI assistance as part of my certification prep. I annotated and reviewed every file to make sure I understand each design decision — the agentic loop, why enforcement belongs in a hook rather than a prompt, how structured errors drive the agent's recovery behavior, and how tool descriptions affect routing. I'm happy to walk through any part of it.
