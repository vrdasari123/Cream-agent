"""General stock research tools, supplementing Robinhood's MCP tools.

Robinhood's agent tools are scoped to the user's own account, positions, and
watchlists (per its support docs); they're not a general market-data API.
For "what's AAPL doing" / "what does NVDA do" style questions, Cream Agent
needs its own read-only data source. This module wraps ``yfinance`` (no API
key required, reasonable default for an open-source project) as an
in-process SDK MCP server. Swapping in a different provider later only
means editing the two ``_fetch_*`` functions below.
"""

from __future__ import annotations

import asyncio
from typing import Any

from claude_agent_sdk import ToolAnnotations, create_sdk_mcp_server, tool

MARKET_DATA_SERVER_NAME = "market_data"

_READ_ONLY = ToolAnnotations(readOnlyHint=True, openWorldHint=True)


def _fetch_quote_sync(ticker: str) -> dict[str, Any]:
    import yfinance as yf

    history = yf.Ticker(ticker).history(period="5d")
    if history.empty:
        return {"symbol": ticker, "last_price": None}

    last = history.iloc[-1]
    prev = history.iloc[-2] if len(history) > 1 else last
    return {
        "symbol": ticker,
        "last_price": round(float(last["Close"]), 2),
        "previous_close": round(float(prev["Close"]), 2),
        "day_high": round(float(last["High"]), 2),
        "day_low": round(float(last["Low"]), 2),
        "volume": int(last["Volume"]) if "Volume" in last else None,
    }


def _fetch_overview_sync(ticker: str) -> dict[str, Any]:
    import yfinance as yf

    info = yf.Ticker(ticker).info or {}
    return {
        "symbol": ticker,
        "short_name": info.get("shortName"),
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "market_cap": info.get("marketCap"),
        "summary": info.get("longBusinessSummary"),
    }


@tool(
    "get_stock_quote",
    "Get the latest price, previous close, and day range for a stock ticker "
    "(e.g. 'what is AAPL trading at', 'how is TSLA doing today'). Read-only; "
    "not connected to any brokerage account.",
    {"ticker": str},
    annotations=_READ_ONLY,
)
async def get_stock_quote(args: dict[str, Any]) -> dict[str, Any]:
    ticker = args["ticker"].strip().upper()
    try:
        data = await asyncio.to_thread(_fetch_quote_sync, ticker)
    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Couldn't fetch a quote for {ticker}: {e}"}],
            "is_error": True,
        }
    if data.get("last_price") is None:
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"No quote data found for ticker '{ticker}'. Double-check the symbol.",
                }
            ],
            "is_error": True,
        }
    text = (
        f"{data['symbol']}: {data['last_price']} "
        f"(prev close {data['previous_close']}, day range {data['day_low']}-{data['day_high']}, "
        f"volume {data['volume']})"
    )
    return {"content": [{"type": "text", "text": text}]}


@tool(
    "get_company_overview",
    "Get a short company profile for a stock ticker: name, sector, industry, "
    "market cap, and a business summary (e.g. 'what does NVDA do', 'what "
    "sector is XOM in'). Read-only; not connected to any brokerage account.",
    {"ticker": str},
    annotations=_READ_ONLY,
)
async def get_company_overview(args: dict[str, Any]) -> dict[str, Any]:
    ticker = args["ticker"].strip().upper()
    try:
        data = await asyncio.to_thread(_fetch_overview_sync, ticker)
    except Exception as e:
        return {
            "content": [{"type": "text", "text": f"Couldn't fetch company info for {ticker}: {e}"}],
            "is_error": True,
        }
    if not data.get("short_name"):
        return {
            "content": [
                {
                    "type": "text",
                    "text": f"No company info found for ticker '{ticker}'. Double-check the symbol.",
                }
            ],
            "is_error": True,
        }
    summary = data.get("summary") or "No summary available."
    if len(summary) > 800:
        summary = summary[:800].rsplit(" ", 1)[0] + "…"
    text = (
        f"{data['short_name']} ({data['symbol']}) — "
        f"{data.get('sector') or 'Unknown sector'} / {data.get('industry') or 'unknown industry'}, "
        f"market cap {data.get('market_cap')}\n{summary}"
    )
    return {"content": [{"type": "text", "text": text}]}


market_data_server = create_sdk_mcp_server(
    name=MARKET_DATA_SERVER_NAME,
    version="0.1.0",
    tools=[get_stock_quote, get_company_overview],
)
