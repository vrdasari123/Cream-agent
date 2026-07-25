# Workflow: Read-Only Account Review

Use this when the user wants a current-state view of their Robinhood account
without discussing orders yet.

## Goal

Produce a concise read-only review of:

- balances and buying power
- current positions
- watchlists
- recent account activity
- obvious follow-up questions

## Rules

- Read-only only.
- Do not prepare or submit orders.
- Distinguish clearly between facts from MCP data and interpretation.
- If required account tools are unavailable, say exactly what is missing.
- Consult `memory/knowledge/preferences.md` and
  `memory/knowledge/risk-limits.md` when present. Missing memory is unknown.
- Follow the event conventions in `AGENTS.md`, including paired `mcp_call` and
  redacted `mcp_result` events for every account read.

## Suggested sequence

1. Emit session/workflow start events and log relevant knowledge reads.
2. Confirm the task is read-only.
3. Inspect balances, buying power, and cash state.
4. Review current positions and position sizing.
5. Review watchlists and recent activity if relevant.
6. Summarize findings, risks, and unanswered questions.
7. If the user wants a durable note, write `memory/journal/YYYY-MM-DD-account-review.md`
   and log the write. Emit workflow/session completion events.

## Output template

```md
# Account Review

Date: YYYY-MM-DD

## Facts
- Buying power:
- Cash:
- Positions reviewed:
- Recent activity reviewed:

## Observations
- 

## Follow-up questions
- 
```
