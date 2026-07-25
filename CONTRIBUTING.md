# Contributing to Cream Agent

Cream Agent's primary product is now a Codex-first workspace layer for
Robinhood Trading MCP. Changes should strengthen durable instructions,
workflow quality, and trading safety before they add more runtime complexity.

## Dev setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Running tests

```bash
pytest
```

Tests avoid hitting Robinhood or Yahoo Finance directly. Legacy OAuth tests use
mocked `httpx` transports, and market-data tests use `monkeypatch`, so the
suite runs offline and deterministically. Set `CREAM_AGENT_HOME` to a temp
directory in any test that touches config or secrets, so it never reads or
writes your real `~/.creamagent`.

## Ground rules

- Read-only-first is the default project posture.
- Anything touching `cream_agent/safety/` or trading workflows gets extra
  scrutiny. Err on the side of stopping, asking, or denying rather than
  allowing.
- No hardcoded secrets, ever.
- The supported onboarding path is client-managed MCP auth, not repo-managed
  OAuth.
- Legacy standalone runtime changes should be treated as quarantine work, not
  product expansion, unless the task explicitly targets legacy cleanup.

## Project layout

Start with [README.md](README.md), [AGENTS.md](AGENTS.md), and the workflow
docs under `docs/workflows/`.
