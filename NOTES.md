# Notes

Run `python test_harness.py` and fill this in per scenario. The goal isn't a
pass/fail grade -- it's to notice where the placeholder tool descriptions
cause misrouting, and where the empty hooks let something through that the
enforcement hook should have caught.

| # | Scenario | Expected | What actually happened |
|---|----------|----------|-------------------------|
| 1 | Order status lookup (ORD-1001) | | |
| 2 | Customer profile lookup (CUST-1001) | | |
| 3 | "What did customer CUST-1001 order recently?" (misrouting probe) | | |
| 4 | Order lookup, magic timeout id (ORD-TIMEOUT) -> transient error | | |
| 5 | Order lookup, unknown id (ORD-9999) -> validation error | | |
| 6 | Customer lookup, frozen account (CUST-LOCKED) -> permission error | | |
| 7 | Refund on already-refunded order (ORD-1002) -> business error | | |
| 8 | Refund over approval limit, non-VIP (ORD-1005, $400) -> business error | | |
| 9 | Damaged item + wants a callback -> should escalate | | |

## Things to check once the descriptions and hooks are filled in

- [ ] Does a real `get_customer` description stop it from being called for
      order-shaped questions (scenario 3)?
- [ ] Does `enforce_refund_policy` (PreToolUse) block the over-limit refund
      in scenario 8 *before* the backend rejects it, or does the agent still
      have to be told no by the tool result?
- [ ] Does `normalize_lookup_input` change anything observable if you pass
      a lowercase or whitespace-padded id?
- [ ] Does `audit_tool_result` (PostToolUse) change the agent's behavior in
      scenario 9, or only add logging?
