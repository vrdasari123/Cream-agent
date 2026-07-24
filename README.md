# Cream Agent

Cream Agent is an open-source, self-hosted AI agent for [Robinhood's Agentic
Trading](https://robinhood.com/us/en/support/articles/agentic-trading-overview/)
integration. You bring your own Claude API key; Cream Agent connects to your
Robinhood **Agentic account** (a dedicated account separate from your primary
brokerage account) over Robinhood's MCP server and lets you chat about
stocks, check your positions, and — in later milestones — execute trades and
build automated trading workflows.

> **Not affiliated with Robinhood.** This is an independent, community
> project. **Nothing in this project is financial advice.** You are solely
> responsible for reviewing and monitoring any activity in your Robinhood
> Agentic account.

## Current status: M1 (read-only)

This build can:
- Answer general stock/company questions using its own market-data tool.
- Read your Robinhood positions, balances, watchlists, and activity, once
  you connect your account.

It **cannot** place, modify, or cancel trades yet. Every Robinhood tool call
is routed through a permission gate (`cream_agent/safety/gate.py`) that
explicitly denies anything that looks like it places an order — trade
execution is a deliberately separate, later milestone with its own
confirmation flow.

## Prerequisites

- Python 3.10+
- **Node.js 18+** — the Claude Agent SDK's Python package drives the Claude
  Code CLI under the hood; Node needs to be on your `PATH`.
- An [Anthropic API key](https://console.anthropic.com/).
- A Robinhood account eligible for Agentic Trading, if you want to connect
  it (optional — the agent works for general stock Q&A without it).

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

## Run

```bash
cream-agent
```

On first run you'll be prompted for your Anthropic API key (stored via your
OS keyring, or a local `~/.creamagent/secrets.json` with owner-only
permissions if no keyring backend is available) and asked whether to connect
Robinhood now. Connecting Robinhood opens a browser for an OAuth consent
flow; Cream Agent implements this itself (see [Architecture](#architecture)
below) since the Agent SDK doesn't run interactive OAuth for library
callers.

In-chat commands:
- `/status` — show MCP server connection status
- `/disconnect-robinhood` — unlink your Robinhood account
- `/quit` — exit

## Architecture

```
cream_agent/
  agent/     Claude Agent SDK wiring: system prompt, options, the chat loop
  mcp/       MCP server configs — Robinhood (external, HTTP) + market data (in-process)
  auth/      Robinhood's OAuth 2.1 + PKCE client (discovery, dynamic client
             registration, local-loopback redirect, token refresh)
  safety/    Permission gate (deny-by-default on trade-shaped tool calls) + audit log
  config/    ~/.creamagent/config.yaml + keyring-backed secrets
  cli/       Chat REPL entrypoint
```

A few decisions worth knowing about if you're reading the code:

- **Why we run our own OAuth client instead of letting the SDK handle it:**
  Anthropic's docs are explicit that the Agent SDK does not open a browser
  or run an interactive OAuth flow for library callers — if a configured MCP
  server demands auth and no token is cached, the SDK just skips that
  server's tools. `cream_agent/auth/robinhood_oauth.py` implements the
  standard MCP authorization flow (RFC 8414/7591/9728 discovery + RFC 8707
  resource indicators) so Cream Agent can get its own bearer token and pass
  it through the SDK's `mcp_servers[...].headers`. This hasn't been
  exercised against Robinhood's real server yet (no interactive browser
  session in this build environment) — Robinhood's docs don't publish exact
  endpoint shapes, so expect to adjust the discovery methods once you can
  test against a live account.

- **Why the safety gate is a runtime callback, not a static allowlist:**
  Robinhood doesn't publish its exact MCP tool names. A wildcard
  `allowed_tools` entry would pre-approve every Robinhood tool — trade tools
  included — without ever going through a permission check. Instead, no
  Robinhood tool is pre-approved; every call is routed through
  `can_use_tool`, which denies anything whose name looks trade-shaped
  (`order`, `trade`, `buy`, `sell`, `cancel`, `place`, `execute`, `submit`)
  and denies anything unrecognized by default. All built-in tools
  (`Bash`, `Write`, etc.) are disabled outright — Cream Agent only acts
  through its two MCP servers.

- **Why yfinance for market data:** Robinhood's own MCP tools are scoped to
  your account/watchlists, not general market research. `yfinance` needs no
  API key, which keeps the "bring your own model, nothing else to sign up
  for" story intact for an open-source project. Swapping providers means
  editing `cream_agent/mcp/market_data.py`.

## Roadmap

- **M2** — trade execution, with per-trade confirmation by default (matching
  Robinhood's own documented default: an agent can trade autonomously only
  if you've explicitly told it to).
- **M3** — natural-language workflows ("DCA $100 into VTI every Friday"),
  scheduled/triggered, routed through the same safety gate as chat-initiated
  trades.
- **M4** — a local web UI (positions, workflow manager, audit log viewer)
  alongside the CLI.
- **M5** — support for the other clients Robinhood's Agentic Trading
  supports (ChatGPT, Cursor, Grok, Codex), beyond the Claude Agent SDK this
  first build is on.

## Development

See [CONTRIBUTING.md](CONTRIBUTING.md).

## License

[MIT](LICENSE)
