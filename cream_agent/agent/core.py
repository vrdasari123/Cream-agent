"""Ties together MCP servers, the safety gate, and the system prompt into a
single agent object the CLI (and later the web UI) drives."""

from __future__ import annotations

import os
from typing import Any, AsyncIterator, Optional

from claude_agent_sdk import ClaudeAgentOptions, ClaudeSDKClient

from cream_agent.agent.prompts import SYSTEM_PROMPT
from cream_agent.auth.robinhood_oauth import RobinhoodOAuthClient
from cream_agent.config.secrets import get_secret
from cream_agent.config.settings import CreamConfig
from cream_agent.mcp.market_data import MARKET_DATA_SERVER_NAME, market_data_server
from cream_agent.mcp.robinhood import ROBINHOOD_SERVER_NAME, build_robinhood_mcp_server
from cream_agent.safety.audit import AuditLogger
from cream_agent.safety.gate import build_can_use_tool


class CreamAgent:
    """Wraps ``ClaudeSDKClient`` with Cream Agent's MCP servers, safety gate,
    and system prompt so callers just deal in prompts and messages.
    """

    def __init__(
        self,
        config: CreamConfig,
        oauth_client: Optional[RobinhoodOAuthClient] = None,
        audit_logger: Optional[AuditLogger] = None,
    ) -> None:
        self.config = config
        self.oauth_client = oauth_client or RobinhoodOAuthClient(
            mcp_url=config.robinhood_mcp_url,
            redirect_port=config.oauth_redirect_port,
        )
        self.audit_logger = audit_logger or AuditLogger()
        self.robinhood_connected = False
        self._client: Optional[ClaudeSDKClient] = None

    def _build_options(self, robinhood_token: Optional[str]) -> ClaudeAgentOptions:
        mcp_servers: dict[str, Any] = {MARKET_DATA_SERVER_NAME: market_data_server}
        if robinhood_token:
            mcp_servers[ROBINHOOD_SERVER_NAME] = build_robinhood_mcp_server(
                access_token=robinhood_token, url=self.config.robinhood_mcp_url
            )

        return ClaudeAgentOptions(
            system_prompt=SYSTEM_PROMPT,
            mcp_servers=mcp_servers,
            # No built-in filesystem/shell/etc. tools: Cream Agent should only
            # ever act through the MCP servers wired in above.
            tools=[],
            allowed_tools=[f"mcp__{MARKET_DATA_SERVER_NAME}__*"],
            can_use_tool=build_can_use_tool(self.audit_logger, trading_enabled=False),
            model=self.config.anthropic_model,
        )

    async def connect(self, interactive_auth: bool = True) -> None:
        """Connect to Claude, wiring in Robinhood if a token is available.

        If ``interactive_auth`` is True and Robinhood isn't connected yet,
        this will open a browser for the OAuth consent flow. Set it to False
        (e.g. for non-interactive/CI use) to skip Robinhood entirely when no
        cached token exists, rather than blocking on a browser flow.
        """
        anthropic_key = get_secret("anthropic_api_key")
        if anthropic_key and not os.environ.get("ANTHROPIC_API_KEY"):
            os.environ["ANTHROPIC_API_KEY"] = anthropic_key

        robinhood_token: Optional[str] = None
        want_robinhood = self.oauth_client.is_connected() or interactive_auth
        if want_robinhood:
            try:
                robinhood_token = self.oauth_client.get_access_token(interactive=interactive_auth)
            except Exception as e:
                print(f"[cream-agent] Robinhood isn't connected ({e}); continuing without it.")
        self.robinhood_connected = robinhood_token is not None

        options = self._build_options(robinhood_token)
        self._client = ClaudeSDKClient(options=options)
        await self._client.connect()

    async def disconnect(self) -> None:
        if self._client is not None:
            await self._client.disconnect()
            self._client = None

    async def ask(self, prompt: str) -> AsyncIterator[Any]:
        if self._client is None:
            raise RuntimeError("CreamAgent.connect() must be called before ask()")
        await self._client.query(prompt)
        async for message in self._client.receive_response():
            yield message

    async def mcp_status(self) -> Any:
        if self._client is None:
            raise RuntimeError("CreamAgent.connect() must be called before mcp_status()")
        return await self._client.get_mcp_status()
