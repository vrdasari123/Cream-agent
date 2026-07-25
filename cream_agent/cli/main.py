"""Offline workspace helpers plus the quarantined legacy standalone CLI."""

from __future__ import annotations

import argparse
import asyncio
import getpass
import json
import sys
from pathlib import Path
from typing import Any

BANNER = """
Cream Agent legacy standalone CLI
This path is quarantined during the MCP-native migration.
Preferred path: configure robinhood-trading MCP in an MCP-capable client, then open this repo there.

Commands: /status  /disconnect-robinhood  /quit
"""


def _ensure_anthropic_key() -> None:
    from cream_agent.config.secrets import get_secret, set_secret

    if get_secret("anthropic_api_key"):
        return
    print("No Anthropic API key found.")
    key = getpass.getpass("Enter your Anthropic API key (input hidden): ").strip()
    if not key:
        print("An Anthropic API key is required to run Cream Agent.", file=sys.stderr)
        sys.exit(1)
    set_secret("anthropic_api_key", key)


def _maybe_connect_robinhood(oauth_client: Any) -> bool:
    if oauth_client.is_connected():
        return True
    answer = input("Connect your Robinhood Agentic account now? [y/N]: ").strip().lower()
    return answer in ("y", "yes")


async def _print_response(agent: Any, prompt: str) -> None:
    from claude_agent_sdk import AssistantMessage, ResultMessage, TextBlock, ToolUseBlock

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


async def legacy_async_main() -> None:
    from cream_agent.agent.core import CreamAgent
    from cream_agent.auth.robinhood_oauth import RobinhoodOAuthClient
    from cream_agent.config.settings import load_config
    from cream_agent.mcp.robinhood import summarize_mcp_status

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


def _json_object(raw: str, label: str) -> dict[str, Any]:
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{label} must be valid JSON: {exc.msg}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{label} must be a JSON object")
    return value


def _workspace_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="cream-agent")
    subparsers = parser.add_subparsers(dest="command")

    log_parser = subparsers.add_parser(
        "log", help="append one validated event without network access"
    )
    log_parser.add_argument("--memory-root", default="memory")
    log_parser.add_argument("--session", required=True)
    log_parser.add_argument("--type", required=True, dest="event_type")
    log_parser.add_argument("--actor", default="agent")
    log_parser.add_argument("--data", default="{}")

    order_parser = subparsers.add_parser(
        "order", help="create or transition a local order record"
    )
    order_subparsers = order_parser.add_subparsers(dest="order_command", required=True)
    create_parser = order_subparsers.add_parser("create")
    create_parser.add_argument("--memory-root", default="memory")
    create_parser.add_argument("--session", required=True)
    create_parser.add_argument("--ticket", required=True)
    create_parser.add_argument("--journal")

    transition_parser = order_subparsers.add_parser("transition")
    transition_parser.add_argument("order_id")
    transition_parser.add_argument("--memory-root", default="memory")
    transition_parser.add_argument("--session", required=True)
    transition_parser.add_argument("--to", required=True, dest="to_state")
    transition_parser.add_argument("--note")
    transition_parser.add_argument("--event-seq", type=int)
    return parser


def _run_workspace_command(args: argparse.Namespace) -> int:
    from cream_agent.memory.events import append_event, event_path
    from cream_agent.memory.orders import (
        ORDER_ID_PATTERN,
        create_order,
        transition_order,
    )

    if args.command == "log":
        event = append_event(
            args.memory_root,
            session=args.session,
            event_type=args.event_type,
            actor=args.actor,
            data=_json_object(args.data, "--data"),
        )
        print(json.dumps(event, sort_keys=True))
        return 0
    if args.command == "order" and args.order_command == "create":
        path, record = create_order(
            args.memory_root,
            session=args.session,
            ticket=_json_object(args.ticket, "--ticket"),
            journal=args.journal,
        )
        event = append_event(
            args.memory_root,
            session=args.session,
            event_type="ticket_created",
            data={
                "order_id": record["id"],
                "path": str(path),
                "ticket_fingerprint": record["ticket_fingerprint"],
            },
        )
        print(
            json.dumps(
                {"path": str(path), "record": record, "event": event}, sort_keys=True
            )
        )
        return 0
    if args.command == "order" and args.order_command == "transition":
        if not ORDER_ID_PATTERN.fullmatch(args.order_id):
            raise ValueError("order_id must match YYYY-MM-DD-SYMBOL-side-NNN")
        memory_root = Path(args.memory_root)
        path = memory_root / "orders" / f"{args.order_id}.json"
        record = transition_order(
            path,
            to_state=args.to_state,
            session=args.session,
            events_path=event_path(memory_root, args.session),
            event_seq=args.event_seq,
            note=args.note,
        )
        event = append_event(
            memory_root,
            session=args.session,
            event_type=(
                "order_submitted"
                if args.to_state == "submitted"
                else "order_status_changed"
            ),
            data={
                "order_id": record["id"],
                "state": record["state"],
                "ticket_fingerprint": record["ticket_fingerprint"],
            },
        )
        print(json.dumps({"record": record, "event": event}, sort_keys=True))
        return 0
    raise ValueError("unsupported command")


def run() -> None:
    parser = _workspace_parser()
    if len(sys.argv) > 1 and sys.argv[1] in {"log", "order"}:
        try:
            raise SystemExit(_run_workspace_command(parser.parse_args()))
        except (OSError, ValueError) as exc:
            parser.error(str(exc))
    try:
        asyncio.run(legacy_async_main())
    except KeyboardInterrupt:
        pass


# Preserve the legacy import surface while keeping helper dispatch offline.
async_main = legacy_async_main


if __name__ == "__main__":
    run()
