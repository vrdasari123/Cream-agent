from cream_agent.mcp import market_data


async def test_get_stock_quote_formats_successful_result(monkeypatch):
    monkeypatch.setattr(
        market_data,
        "_fetch_quote_sync",
        lambda ticker: {
            "symbol": ticker,
            "last_price": 190.5,
            "previous_close": 188.0,
            "day_high": 191.0,
            "day_low": 187.5,
            "volume": 1000000,
        },
    )
    result = await market_data.get_stock_quote.handler({"ticker": "aapl"})
    assert result.get("is_error") is not True
    text = result["content"][0]["text"]
    assert "AAPL" in text
    assert "190.5" in text


async def test_get_stock_quote_handles_unknown_ticker(monkeypatch):
    monkeypatch.setattr(
        market_data, "_fetch_quote_sync", lambda ticker: {"symbol": ticker, "last_price": None}
    )
    result = await market_data.get_stock_quote.handler({"ticker": "ZZZZINVALID"})
    assert result["is_error"] is True


async def test_get_stock_quote_handles_fetch_exception(monkeypatch):
    def _raise(ticker):
        raise RuntimeError("network down")

    monkeypatch.setattr(market_data, "_fetch_quote_sync", _raise)
    result = await market_data.get_stock_quote.handler({"ticker": "AAPL"})
    assert result["is_error"] is True
    assert "network down" in result["content"][0]["text"]


async def test_get_company_overview_formats_and_truncates_long_summary(monkeypatch):
    long_summary = "word " * 300
    monkeypatch.setattr(
        market_data,
        "_fetch_overview_sync",
        lambda ticker: {
            "symbol": ticker,
            "short_name": "Example Corp",
            "sector": "Technology",
            "industry": "Software",
            "market_cap": 123456789,
            "summary": long_summary,
        },
    )
    result = await market_data.get_company_overview.handler({"ticker": "EX"})
    text = result["content"][0]["text"]
    assert "Example Corp" in text
    assert len(text) < len(long_summary) + 200


async def test_get_company_overview_handles_unknown_ticker(monkeypatch):
    monkeypatch.setattr(
        market_data, "_fetch_overview_sync", lambda ticker: {"symbol": ticker, "short_name": None}
    )
    result = await market_data.get_company_overview.handler({"ticker": "ZZZZINVALID"})
    assert result["is_error"] is True
