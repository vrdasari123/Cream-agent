from cream_agent.safety.audit import AuditLogger


def test_log_and_read_all_round_trip(tmp_path):
    logger = AuditLogger(path=tmp_path / "audit.log")
    logger.log("mcp__robinhood__get_positions", {"account": "abc"}, decision="allow")
    logger.log(
        "mcp__robinhood__place_order",
        {"symbol": "AAPL", "qty": 1},
        decision="deny",
        reason="trading disabled",
    )

    entries = logger.read_all()
    assert len(entries) == 2
    assert entries[0]["tool_name"] == "mcp__robinhood__get_positions"
    assert entries[0]["decision"] == "allow"
    assert entries[0]["reason"] is None
    assert entries[1]["decision"] == "deny"
    assert entries[1]["reason"] == "trading disabled"


def test_read_all_on_missing_file_returns_empty_list(tmp_path):
    logger = AuditLogger(path=tmp_path / "nope.log")
    assert logger.read_all() == []


def test_log_creates_parent_directory(tmp_path):
    nested = tmp_path / "nested" / "dir" / "audit.log"
    logger = AuditLogger(path=nested)
    logger.log("some_tool", {}, decision="allow")
    assert nested.exists()
