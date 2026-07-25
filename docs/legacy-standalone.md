# Legacy Standalone Path

This repo previously centered on a standalone Python application built around
the Claude Agent SDK, Anthropic API keys, and a custom Robinhood OAuth client.
That is no longer Cream Agent's primary product direction.

## Status

As of July 25, 2026:

- supported path: open/use the repo in an MCP-capable client after configuring
  Robinhood Trading MCP there
- verified today: Codex
- future client targets: Claude, Cursor, Windsurf, Kimi, ChatGPT, and other
  MCP-capable clients
- unsupported primary path: use Cream Agent as a self-contained standalone app
  that handles Robinhood authentication itself

## Why it is quarantined

The old path is misaligned with the new product goals:

- it duplicates capabilities the MCP-capable client should own
- it introduces a custom Robinhood OAuth surface for end users
- it requires an Anthropic key flow that is no longer part of the primary
  onboarding
- it makes Cream Agent feel like a separate app instead of a durable workspace
  layer

## What still remains in code

These areas still exist for now:

- `cream_agent/agent/`
- `cream_agent/auth/`
- `cream_agent/cli/`

They are retained to keep this migration scoped and low-risk. Future cleanup
can remove or archive them once the MCP-native workspace layer is fully
established.
