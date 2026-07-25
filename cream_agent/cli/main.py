"""Legacy standalone CLI retained during the Codex-first migration."""

from __future__ import annotations

import asyncio
import getpass
import sys

from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock, ToolUseBlock

from cream_agent.agent.core import CreamAgent
from cream_agent.auth.robinhood_oauth import RobinhoodOAuthClient
from cream_agent.config.secrets import get_secret, set_secret
from cream_agent.config.settings import load_config
from cream_agent.mcp.robinhood import summarize_mcp_status

BANNER = """
Cream Agent legacy standalone CLI
This path is quarantined during the Codex-first migration.
Preferred path: configure robinhood-trading MCP in Codex, then open this repo in Codex.

Commands: /status  /disconnect-robinhood  /quit
"""


def _ensure_anthropic_key() -> None:
    if get_secret("anthropic_api_key"):
        return
    print("No Anthropic API key found.")
    key = getpass.getpass("Enter your Anthropic API key (input hidden): ").strip()
    if not key:
        print("An Anthropic API key is required to run Cream Agent.", file=sys.stderr)
        sys.exit(1)
    set_secret("anthropic_api_key", key)


def _maybe_connect_robinhood(oauth_client: RobinhoodOAuthClient) -> bool:
    if oauth_client.is_connected():
        return True
    answer = input("Connect your Robinhood Agentic account now? [y/N]: ").strip().lower()
    return answer in ("y", "yes")


async def _print_response(agent: CreamAgent, prompt: str) -> None:
    async for message in agent.ask(prompt):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, TextBlock):
                    print(block.text)
                elif isinstance(block, ToolUseBlock):
                    print(f"  [tool call] {block.name}({block.input})")
        elif isinstance(message, ResultMessage):
            if message.subtype != "success":
                print(f"[cream-agent] {message.subtype}: {message.result}")


async def async_main() -> None:
    print(BANNER)
    _ensure_anthropic_key()
    config = load_config()
    oauth_client = RobinhoodOAuthClient(
        mcp_url=config.robinhood_mcp_url, redirect_port=config.oauth_redirect_port
    )
    want_robinhood = _maybe_connect_robinhood(oauth_client)

    agent = CreamAgent(config=config, oauth_client=oauth_client)
    await agent.connect(interactive_auth=want_robinhood)

    if agent.robinhood_connected:
        print("[cream-agent] Robinhood connected.")
    else:
        print("[cream-agent] Running without Robinhood — general stock Q&A only.")

    try:
        while True:
            try:
                prompt = input("\nyou> ").strip()
            except EOFError:
                break
            if not prompt:
                continue
            if prompt in ("/quit", "/exit"):
                break
            if prompt == "/status":
                status = await agent.mcp_status()
                print(summarize_mcp_status(status))
                continue
            if prompt == "/disconnect-robinhood":
                oauth_client.disconnect()
                print("[cream-agent] Robinhood disconnected. Restart to reconnect.")
                continue
            await _print_response(agent, prompt)
    finally:
        await agent.disconnect()
        oauth_client.close()


def run() -> None:
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    run()
