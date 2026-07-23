"""The M1 permission gate: a hard, non-optional deny on anything that trades.

Design note: we deliberately do *not* pre-approve Robinhood's tools via
``allowed_tools`` wildcards, because Robinhood doesn't publish its exact MCP
tool names and a wildcard would pre-approve trade-placing tools right along
with read-only ones. Instead every Robinhood tool call — read-only or not —
is routed through this ``can_use_tool`` callback, which is the one place
that decides what's safe to run. Everything not explicitly recognized here
is denied by default.
"""

from __future__ import annotations

from typing import Any

from claude_agent_sdk import PermissionResultAllow, PermissionResultDeny, ToolPermissionContext

from cream_agent.mcp.robinhood import ROBINHOOD_SERVER_NAME, is_trade_tool
from cream_agent.safety.audit import AuditLogger

_ROBINHOOD_PREFIX = f"mcp__{ROBINHOOD_SERVER_NAME}__"


def build_can_use_tool(audit_logger: AuditLogger, trading_enabled: bool = False):
    """Build the SDK's ``can_use_tool`` permission callback.

    ``trading_enabled`` exists as a parameter (rather than being hardcoded
    inline) so M2's confirmation flow can flip it on for a session without
    rewriting this gate — but every M1 caller passes ``False``, and M1 has
    no code path that sets it otherwise.
    """

    async def can_use_tool(
        tool_name: str, input_data: dict[str, Any], context: ToolPermissionContext
    ):
        if tool_name.startswith(_ROBINHOOD_PREFIX):
            if is_trade_tool(tool_name) and not trading_enabled:
                audit_logger.log(
                    tool_name=tool_name,
                    input_data=input_data,
                    decision="deny",
                    reason="Trade-shaped tool call blocked: trading isn't enabled in this build.",
                )
                return PermissionResultDeny(
                    message=(
                        "Cream Agent can't place, modify, or cancel orders yet — "
                        "trade execution ships in a later milestone with its own "
                        "confirmation flow. This session is read-only."
                    )
                )
            audit_logger.log(tool_name=tool_name, input_data=input_data, decision="allow")
            return PermissionResultAllow(updated_input=input_data)

        audit_logger.log(
            tool_name=tool_name,
            input_data=input_data,
            decision="deny",
            reason="Tool not on Cream Agent's allowlist.",
        )
        return PermissionResultDeny(message=f"Tool '{tool_name}' is not enabled in Cream Agent.")

    return can_use_tool
