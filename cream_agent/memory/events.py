"""Versioned JSONL event schema and atomic append helper."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any, Mapping

from .common import exclusive_lock, parse_timestamp, utc_now

EVENT_VERSION = 1
EVENT_TYPES = frozenset(
    {
        "session_started",
        "session_completed",
        "workflow_started",
        "workflow_completed",
        "memory_read",
        "memory_write",
        "mcp_call",
        "mcp_result",
        "decision",
        "ticket_created",
        "ticket_updated",
        "confirmation_requested",
        "confirmation_received",
        "order_submitted",
        "order_status_changed",
        "journal_written",
    }
)
ACTORS = frozenset({"agent", "client", "mcp", "system", "user"})
SESSION_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
EVENT_KEYS = frozenset({"v", "ts", "session", "seq", "type", "actor", "data"})


class EventValidationError(ValueError):
    """Raised when an event does not conform to event schema v1."""


def validate_event(event: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(event, Mapping):
        raise EventValidationError("event must be a JSON object")
    unknown = set(event) - EVENT_KEYS
    missing = EVENT_KEYS - set(event)
    if missing:
        raise EventValidationError(f"missing event fields: {', '.join(sorted(missing))}")
    if unknown:
        raise EventValidationError(f"unknown event fields: {', '.join(sorted(unknown))}")
    if event["v"] != EVENT_VERSION:
        raise EventValidationError(f"v must be {EVENT_VERSION}")
    try:
        parse_timestamp(event["ts"], "ts")
    except ValueError as exc:
        raise EventValidationError(str(exc)) from exc
    if not isinstance(event["session"], str) or not SESSION_PATTERN.fullmatch(
        event["session"]
    ):
        raise EventValidationError("session must be a safe 1-128 character identifier")
    if not isinstance(event["seq"], int) or isinstance(event["seq"], bool):
        raise EventValidationError("seq must be an integer")
    if event["seq"] < 1:
        raise EventValidationError("seq must be at least 1")
    if event["type"] not in EVENT_TYPES:
        raise EventValidationError(f"unsupported event type: {event['type']!r}")
    if event["actor"] not in ACTORS:
        raise EventValidationError(f"unsupported actor: {event['actor']!r}")
    if not isinstance(event["data"], dict):
        raise EventValidationError("data must be a JSON object")
    return dict(event)


def event_path(memory_root: Path | str, session: str) -> Path:
    if not isinstance(session, str) or not SESSION_PATTERN.fullmatch(session):
        raise EventValidationError("session must be a safe 1-128 character identifier")
    return Path(memory_root) / "events" / f"{session}.jsonl"


def read_events(path: Path | str) -> list[dict[str, Any]]:
    source = Path(path)
    if not source.exists():
        return []
    events: list[dict[str, Any]] = []
    with source.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                parsed = json.loads(line)
            except json.JSONDecodeError as exc:
                raise EventValidationError(
                    f"{source}:{line_number}: invalid JSON: {exc.msg}"
                ) from exc
            events.append(validate_event(parsed))
    _validate_sequence(events, source)
    return events


def _validate_sequence(events: list[dict[str, Any]], source: Path) -> None:
    for expected, event in enumerate(events, 1):
        if event["seq"] != expected:
            raise EventValidationError(
                f"{source}: expected seq {expected}, found {event['seq']}"
            )


def append_event(
    memory_root: Path | str,
    *,
    session: str,
    event_type: str,
    data: Mapping[str, Any],
    actor: str = "agent",
    timestamp: str | None = None,
) -> dict[str, Any]:
    """Validate and append one event under a cross-process session lock."""

    path = event_path(memory_root, session)
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.with_suffix(path.suffix + ".lock")
    with exclusive_lock(lock_path):
        existing = read_events(path)
        if any(event["session"] != session for event in existing):
            raise EventValidationError(
                f"{path}: contains an event for a different session"
            )
        event = validate_event(
            {
                "v": EVENT_VERSION,
                "ts": timestamp or utc_now(),
                "session": session,
                "seq": len(existing) + 1,
                "type": event_type,
                "actor": actor,
                "data": dict(data),
            }
        )
        encoded = (
            json.dumps(event, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
            + "\n"
        ).encode()
        descriptor = os.open(path, os.O_APPEND | os.O_CREAT | os.O_WRONLY, 0o600)
        try:
            written = os.write(descriptor, encoded)
            if written != len(encoded):  # pragma: no cover - defensive OS condition
                raise OSError("short write while appending event")
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        return event
