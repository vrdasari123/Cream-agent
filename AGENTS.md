# Cream Agent Repo Instructions

Cream Agent is a Codex-first trading workspace layered on top of Robinhood
Trading MCP. This repo does not own user authentication, does not run a custom
Robinhood OAuth flow for the supported product path, and does not require an
Anthropic API key for the primary experience.

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
  [docs/workflows/account-review.md](/Users/work/.codex/worktrees/17f2/Cream Agent/docs/workflows/account-review.md)
- Portfolio and risk review:
  [docs/workflows/portfolio-risk-review.md](/Users/work/.codex/worktrees/17f2/Cream Agent/docs/workflows/portfolio-risk-review.md)
- Order ticket preparation:
  [docs/workflows/order-ticket.md](/Users/work/.codex/worktrees/17f2/Cream Agent/docs/workflows/order-ticket.md)

## Artifacts

- Prefer producing compact, reusable artifacts instead of one-off chat-only
  answers.
- When a review is substantial, suggest or create a dated note under
  `docs/journal/` if the user wants a saved artifact.
- Keep any saved artifact factual and clearly separate tool-derived facts from
  reasoning or opinion.

## Legacy code boundary

- The Python standalone app in `cream_agent/agent`, `cream_agent/auth`, and
  `cream_agent/cli` is legacy and quarantined.
- Do not present that path as the default product unless the user explicitly
  asks about legacy implementation status.
- If touching legacy code, preserve the repo's stricter safety posture and do
  not loosen trade controls.
