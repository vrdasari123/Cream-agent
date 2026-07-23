from cream_agent.mcp.robinhood import build_robinhood_mcp_server, summarize_mcp_status


def test_build_robinhood_mcp_server_shape():
    server = build_robinhood_mcp_server("token123", "https://agent.robinhood.com/mcp/trading")
    assert server == {
        "type": "http",
        "url": "https://agent.robinhood.com/mcp/trading",
        "headers": {"Authorization": "Bearer token123"},
    }


def test_summarize_mcp_status_with_dict_shape():
    status = {"servers": [{"name": "robinhood", "status": "connected"}]}
    summary = summarize_mcp_status(status)
    assert "robinhood" in summary
    assert "connected" in summary


def test_summarize_mcp_status_handles_missing_servers():
    assert "No MCP server status" in summarize_mcp_status({})
