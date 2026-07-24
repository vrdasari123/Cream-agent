"""Wiring for Robinhood's Agentic Trading MCP server into the Agent SDK."""

from __future__ import annotations

from typing import Any

ROBINHOOD_SERVER_NAME = "robinhood"

# Tool name substrings that mean "this places, modifies, or cancels an
# order" — anything matching is trade-shaped and, in M1, is never allowed to
# run (see cream_agent.safety.gate). This is a denylist, not an allowlist,
# because Robinhood's exact MCP tool names aren't published; a denylist over
# the discovered tool list is more robust to naming we haven't seen than
# hardcoding names we're guessing at.
TRADE_TOOL_KEYWORDS = (
    "order",
    "trade",
    "buy",
    "sell",
    "cancel",
    "place",
    "execute",
    "submit",
)

# Prefixes that mean "this only reads/returns data" — the *only* basis on
# which cream_agent.safety.gate allows a Robinhood tool to run. This is an
# allowlist, not the denylist above: a Robinhood tool call is denied unless
# its bare name starts with one of these, so an unrecognized tool (one whose
# name doesn't happen to match a trade keyword *or* a read-only prefix, e.g.
# a hypothetical "create_position" or "withdraw_cash") fails closed instead
# of being silently allowed.
READ_ONLY_TOOL_PREFIXES = (
    "get_",
    "list_",
    "fetch_",
    "read_",
    "view_",
    "describe_",
)


def build_robinhood_mcp_server(access_token: str, url: str) -> dict[str, Any]:
    """Build the ``mcp_servers`` entry the Agent SDK expects for Robinhood.

    The Agent SDK doesn't run OAuth for library callers (see
    ``cream_agent.auth.robinhood_oauth``), so the bearer token obtained
    there is passed straight through as an HTTP header, per the MCP spec's
    "Access Token Usage" section.
    """
    return {
        "type": "http",
        "url": url,
        "headers": {"Authorization": f"Bearer {access_token}"},
    }


def is_trade_tool(tool_name: str) -> bool:
    """Best-effort classification of whether an MCP tool can move money.

    ``tool_name`` is the fully-qualified ``mcp__<server>__<tool>`` name (or
    just the bare tool name — matching is substring-based either way).
    """
    lowered = tool_name.lower()
    return any(keyword in lowered for keyword in TRADE_TOOL_KEYWORDS)


def is_read_only_tool(tool_name: str) -> bool:
    """Whether ``tool_name`` is provably read-only, i.e. safe to allow even
    though Robinhood hasn't published its exact tool names.

    ``tool_name`` may be fully-qualified (``mcp__robinhood__get_positions``)
    or bare (``get_positions``) — only the last ``__``-separated segment is
    checked against :data:`READ_ONLY_TOOL_PREFIXES`. A tool must also not be
    trade-shaped per :func:`is_trade_tool`, so a name like ``get_order_status``
    still fails closed rather than being allowed on prefix alone.
    """
    bare = tool_name.lower().rsplit("__", 1)[-1]
    return bare.startswith(READ_ONLY_TOOL_PREFIXES) and not is_trade_tool(tool_name)


def summarize_mcp_status(status: Any) -> str:
    """Render an SDK ``McpStatusResponse``-like object into a short,
    human-readable line per server, for the CLI's startup banner.
    """
    servers = getattr(status, "servers", None)
    if servers is None and isinstance(status, dict):
        servers = status.get("servers") or status.get("mcp_servers")
    if not servers:
        return "No MCP server status available."

    lines = []
    for server in servers:
        name = server.get("name") if isinstance(server, dict) else getattr(server, "name", "?")
        state = (
            server.get("status") if isinstance(server, dict) else getattr(server, "status", "?")
        )
        lines.append(f"  - {name}: {state}")
    return "\n".join(lines)
