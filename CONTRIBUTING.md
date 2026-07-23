# Contributing to Cream Agent

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

Tests avoid hitting Robinhood, Anthropic, or Yahoo Finance directly — network
calls are mocked (`httpx.MockTransport` for OAuth, `monkeypatch` for
`yfinance`-backed functions) so the suite runs offline and deterministically.
Set `CREAM_AGENT_HOME` to a temp directory in any test that touches config or
secrets, so it never reads or writes your real `~/.creamagent`.

## Ground rules

- This project handles real brokerage access and real trades once trading
  ships (M2+). Anything touching `cream_agent/safety/` or the Robinhood tool
  wiring gets extra scrutiny — err on the side of denying by default rather
  than allowing.
- No hardcoded secrets, ever — API keys and tokens go through
  `cream_agent.config.secrets`.
- Keep new external MCP integrations behind the same "deny unless explicitly
  classified safe" pattern used for Robinhood in
  `cream_agent/safety/gate.py`, rather than pre-approving with a wildcard.

## Project layout

See the Architecture section in [README.md](README.md).
