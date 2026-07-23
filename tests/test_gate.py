import pytest
from claude_agent_sdk import PermissionResultAllow, PermissionResultDeny

from cream_agent.mcp.robinhood import is_trade_tool
from cream_agent.safety.audit import AuditLogger
from cream_agent.safety.gate import build_can_use_tool


@pytest.fixture
def gate(tmp_path):
    logger = AuditLogger(path=tmp_path / "audit.log")
    return build_can_use_tool(logger, trading_enabled=False), logger


@pytest.mark.parametrize(
    "tool_name",
    [
        "mcp__robinhood__place_order",
        "mcp__robinhood__cancel_order",
        "mcp__robinhood__submit_trade",
        "mcp__robinhood__buy_equity",
    ],
)
async def test_trade_shaped_robinhood_tools_are_denied(gate, tool_name):
    can_use_tool, logger = gate
    result = await can_use_tool(tool_name, {"symbol": "AAPL"}, context=None)
    assert isinstance(result, PermissionResultDeny)
    entries = logger.read_all()
    assert entries[-1]["decision"] == "deny"


@pytest.mark.parametrize(
    "tool_name",
    [
        "mcp__robinhood__get_positions",
        "mcp__robinhood__get_watchlists",
        "mcp__robinhood__get_account_balances",
    ],
)
async def test_read_only_robinhood_tools_are_allowed(gate, tool_name):
    can_use_tool, logger = gate
    result = await can_use_tool(tool_name, {}, context=None)
    assert isinstance(result, PermissionResultAllow)
    entries = logger.read_all()
    assert entries[-1]["decision"] == "allow"


async def test_unrecognized_tool_is_denied_by_default(gate):
    can_use_tool, logger = gate
    result = await can_use_tool("Bash", {"command": "rm -rf /"}, context=None)
    assert isinstance(result, PermissionResultDeny)


def test_is_trade_tool_classifier():
    assert is_trade_tool("mcp__robinhood__place_order")
    assert is_trade_tool("mcp__robinhood__cancel_order")
    assert not is_trade_tool("mcp__robinhood__get_positions")
    assert not is_trade_tool("mcp__market_data__get_stock_quote")
