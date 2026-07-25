# Cream Agent Repo Instructions

Cream Agent is an MCP-native trading workspace layered on top of Robinhood
Trading MCP. Codex is the first verified client, but the repo is designed to be
portable to any MCP-capable client that can add/login Robinhood Trading MCP and
use repo instructions/workflows. This repo does not own user authentication,
does not run a custom Robinhood OAuth flow for the supported product path, and
does not require an Anthropic API key for the primary experience.

## Operating mode

- Default to read-only behavior.
- Treat brokerage actions as high-risk and irreversible unless proven
  otherwise.
- Prefer reviewing account state, portfolio risk, positions, balances,
  watchlists, and recent activity before suggesting action.
- Use Robinhood Trading MCP only through the user's own configured client
  connection.

## Trade safety rules

- Never submit, modify, or cancel an order unless the user explicitly asks for
  that action.
- Never infer missing order fields.
- Before any live order action, require all of:
  - symbol
  - side
  - quantity or notional
  - order type
  - limit/stop price when relevant
  - time in force
- Before any live order action, restate the full order ticket and ask for a
  final confirmation in the same interaction.
- If the user asks for analysis only, do not escalate into order preparation
  or submission.
- If the user asks to "buy", "sell", or "place an order" without exact terms,
  stop and collect the missing fields.
- If the user asks to prepare an order ticket, do not submit it. Produce the
  ticket, risk notes, and explicit next-step wording only.

## Workflow routing

When the user intent matches one of these workflows, use the corresponding doc:

- Account review:
  [docs/workflows/account-review.md](docs/workflows/account-review.md)
- Portfolio and risk review:
  [docs/workflows/portfolio-risk-review.md](docs/workflows/portfolio-risk-review.md)
- Order ticket preparation:
  [docs/workflows/order-ticket.md](docs/workflows/order-ticket.md)

## Artifacts

- Prefer producing compact, reusable artifacts instead of one-off chat-only
  answers.
- When a review is substantial, suggest or create a dated note under
  `memory/journal/` if the user wants a saved artifact.
- Keep any saved artifact factual and clearly separate tool-derived facts from
  reasoning or opinion.

## Private memory conventions

`memory/` is the private runtime data plane and is ignored by git by default.
Never put real account data, order records, session events, or personal notes
under tracked `templates/`. Safe starter files live under `templates/memory/`.

At the beginning of a task:

1. Choose a safe session ID containing only letters, digits, `.`, `_`, or `-`.
2. Emit `session_started` with `cream-agent log`.
3. Read only the knowledge files relevant to the workflow. Log each consulted
   path as `memory_read`; absence means unknown, not permission.
4. Emit `workflow_started` before following a workflow document.

During a task:

- Emit `mcp_call` immediately before every Robinhood Trading MCP call, naming
  the tool and operation but excluding credentials and unnecessary sensitive
  payloads.
- Emit `mcp_result` immediately after it with outcome and a redacted summary.
- Emit `memory_read` and `memory_write` for every private memory file used.
- Emit `decision` for material reasoning or a safety stop.
- Never store credentials, tokens, consent artifacts, or full raw MCP
  responses in memory.

At completion:

- Write substantial factual notes to `memory/journal/` when requested and emit
  `journal_written`.
- Emit `workflow_completed`, then `session_completed`. If stopped or blocked,
  record that outcome rather than pretending the workflow completed.

Example:

```bash
cream-agent log --session 2026-07-25-review-001 \
  --type session_started --data '{"purpose":"read-only account review"}'
```

The helper validates schema v1 and atomically appends to
`memory/events/<session>.jsonl`. It is stdlib-only and never uses the network,
MCP, brokerage APIs, authentication, or consent. If the installed entry point
is unavailable, use `python -m cream_agent.cli.main` with the same arguments.

## Order records and confirmation

- Preparing a complete ticket creates `memory/orders/<order-id>.json` in
  `draft`; it does not authorize or submit anything.
- Consult `memory/knowledge/risk-limits.md`,
  `memory/knowledge/preferences.md`, and a matching ticker thesis when present.
  Surface conflicts before confirmation.
- A live order request requires a `confirmation_requested` event containing
  the order ID and exact ticket fingerprint, followed by a user-authored
  `confirmation_received` event for those same values in the same session.
- Move a record to `confirmed` only after that final confirmation.
- Move it to `submitted` only after the live MCP submission succeeds. The
  offline state helper rejects this transition unless the matching
  `confirmation_received` event exists.
- Record fills, partial fills, cancellation, rejection, or abandonment as
  explicit legal transitions. Files are replaced atomically; history is
  append-only within each record.
- Recording a state never performs the brokerage action. The agent/client owns
  all MCP calls and remains bound by the trade safety rules above.

## Legacy code boundary

- The Python standalone app in `cream_agent/agent`, `cream_agent/auth`, and
  `cream_agent/cli` is legacy and quarantined.
- Do not present that path as the default product unless the user explicitly
  asks about legacy implementation status.
- If touching legacy code, preserve the repo's stricter safety posture and do
  not loosen trade controls.
