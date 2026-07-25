# Cream Agent

Cream Agent is a Codex-first trading workspace for Robinhood Trading MCP. It
is not another chat app, not a hosted agent service, and not a replacement for
your MCP-capable client. You clone this repo, connect Robinhood Trading MCP in
your own client, then open Codex from inside this folder so the repo's durable
instructions, workflows, and safety rules are loaded with the session.

> **Not affiliated with Robinhood.** This is an independent project.
> **Nothing in this repo is financial advice.** You are responsible for every
> order, approval, and portfolio decision.
> **Cream Agent is not a trading bot, not a login provider, and not a
> replacement for your judgment.** It is a disciplined operating layer for how
> you use Codex with Robinhood Trading MCP.

## Why this exists

If you already have Codex and Robinhood Trading MCP, the obvious question is:
why clone another repo at all?

Because plain Codex gives you raw MCP access, but not a persistent trading
operating layer. Without a repo like this, you either trade from ad hoc prompts
or rewrite your own rules each session.

Cream Agent exists to make your trading workflow more disciplined:

- persistent trading safety rules that load with the repo
- repeatable account review and portfolio/risk review workflows
- explicit order-ticket friction before any live order action
- audit and journal conventions so decisions do not disappear into chat history
- a portable workspace structure that can later move to other MCP-capable
  clients

In product terms: Codex is the general-purpose engine. Cream Agent is the
trading operating layer you keep around it.

## Product direction

As of July 25, 2026, Cream Agent's primary product is:

- A persistent trading policy layer on top of Codex.
- Read-only-first workflows for account review and portfolio/risk review.
- An explicit order ticket workflow that prepares a trade without submitting it.
- Durable artifacts for notes, auditability, and later portability to other
  MCP-capable clients.

Cream Agent is **not**:

- A standalone M1 chat application.
- An Anthropic API key flow.
- A custom Robinhood OAuth implementation for end users.

Legacy Python code for the earlier standalone path still exists in this repo,
but it is quarantined and no longer the recommended product surface. See
[docs/legacy-standalone.md](docs/legacy-standalone.md).

## Why use Cream Agent instead of plain Codex?

| Plain Codex + MCP | Cream Agent |
| --- | --- |
| Raw tool access | Raw tool access plus persistent trading discipline |
| Prompts are easy to improvise and forget | Workflows and safety rules live in the repo |
| Order handling depends on what you remember to ask | Order-ticket preparation and final confirmation are explicit |
| Notes often stay trapped in chat history | Journal and audit conventions are part of the workflow |
| Portable only if you rebuild your setup elsewhere | Structured to be portable to future MCP-capable clients |

Cream Agent is for users who want Codex to behave less like a blank terminal
and more like a consistent trading workspace.

## User journey

### 1. Clone the repo

```bash
git clone https://github.com/<your-org-or-user>/Cream-agent.git
cd Cream-agent
```

### 2. Add Robinhood Trading MCP in Codex

Run these commands exactly:

```bash
codex mcp add robinhood-trading --url https://agent.robinhood.com/mcp/trading
codex mcp login robinhood-trading
codex mcp list
```

Cream Agent does **not** run Robinhood login itself. Authentication belongs to
your MCP client.

### 3. Open Codex inside this repo

From inside the repo folder:

```bash
codex
```

Opening Codex here matters because the repo contains durable instructions in
[AGENTS.md](AGENTS.md) and reusable workflow docs under
[docs/workflows](docs/workflows).

### 4. Use the workflows and safety rules

Start from a read-only task, then escalate only if you intentionally want to
prepare an order ticket:

- account review
- portfolio and risk review
- draft order ticket preparation without submission

### 5. Keep decisions durable

Use the repo's journal and workflow conventions so important trade reasoning,
risk notes, and prepared tickets do not vanish into a single chat session.

## Quick start

### 1. Install and verify Codex

Cream Agent assumes you already have the `codex` CLI available on your machine.

What you should see:

- `robinhood-trading` appears in `codex mcp list`
- the server is available to Codex in your client environment

### 2. Run the local doctor check

```bash
python3 -m cream_agent.doctor
```

Or, if installed as a package:

```bash
cream-agent-doctor
```

This check is read-only. It looks for:

- the `codex` executable
- whether `codex mcp list` runs
- whether `robinhood-trading` appears in that local MCP configuration

It does not place trades, fetch account data, or modify Codex settings.

## Session model

Cream Agent sessions should start read-only and stay there unless the user
clearly asks to prepare or submit a trade.

Recommended starting prompts:

- "Run the account review workflow with read-only tools only."
- "Review portfolio concentration and risk exposures. Do not propose orders yet."
- "Prepare an order ticket for buying 5 shares of VTI as a day limit order at
  275.00. Do not submit anything."

Relevant workflow docs:

- [docs/workflows/account-review.md](docs/workflows/account-review.md)
- [docs/workflows/portfolio-risk-review.md](docs/workflows/portfolio-risk-review.md)
- [docs/workflows/order-ticket.md](docs/workflows/order-ticket.md)

## Safety policy

Cream Agent's default trading policy is intentionally strict:

- Read-only is the default mode.
- Preparing an order ticket is allowed before submission.
- Submitting, modifying, or canceling an order requires exact terms from the
  user.
- Live order actions require a final confirmation immediately before the tool
  call.
- If order terms are ambiguous, stale, inferred, or incomplete, the session
  must stop and ask for clarification.
- If risk checks surface missing context, the agent should pause before any
  live action.

Minimum order fields before any live submission:

- side
- symbol
- quantity or notional
- order type
- limit or stop price when applicable
- time in force

Cream Agent should also restate the full order ticket back to the user just
before final confirmation.

## Repo layout

```text
AGENTS.md                 Durable Codex operating instructions
docs/workflows/           Repeatable trading workflows and templates
cream_agent/doctor.py     Local read-only onboarding/doctor check
cream_agent/              Legacy standalone runtime, now quarantined
tests/                    Safety, config, and utility tests
```

## Current migration boundary

This first Codex-first release updates the repo's operating layer and local
checks. It does **not** yet remove every legacy module from the old standalone
app architecture.

What changed now:

- top-level docs now describe the Codex-first workflow
- durable session rules live in `AGENTS.md`
- workflow templates exist for read-only review and order preparation
- a read-only doctor utility checks local Codex/MCP setup

What remains quarantined for a later pass:

- the standalone Claude SDK runtime
- Anthropic-key prompts in the legacy CLI
- custom Robinhood OAuth helper code used only by that legacy path

Those legacy surfaces are no longer the supported onboarding path.

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md).

Run tests with:

```bash
pytest
```

## License

[MIT](LICENSE)
