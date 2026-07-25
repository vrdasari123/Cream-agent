from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from cream_agent.memory.events import (
    EVENT_TYPES,
    EventValidationError,
    append_event,
    read_events,
    validate_event,
)
from cream_agent.memory.orders import (
    OrderValidationError,
    create_order,
    ticket_fingerprint,
    transition_order,
    validate_order,
    validate_ticket,
)
from cream_agent.memory.snapshots import SnapshotValidationError, validate_snapshot

TICKET = {
    "symbol": "VTI",
    "side": "buy",
    "quantity": "5",
    "order_type": "limit",
    "limit_price": "275.00",
    "time_in_force": "day",
}


def test_event_schema_accepts_every_vocabulary_type() -> None:
    for event_type in EVENT_TYPES:
        assert validate_event(
            {
                "v": 1,
                "ts": "2026-07-25T12:00:00Z",
                "session": "session-1",
                "seq": 1,
                "type": event_type,
                "actor": "agent",
                "data": {},
            }
        )["type"] == event_type


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("v", 2),
        ("ts", "not-a-time"),
        ("session", "../escape"),
        ("seq", 0),
        ("type", "arbitrary"),
        ("actor", "broker"),
        ("data", []),
    ],
)
def test_event_schema_rejects_invalid_fields(field: str, value: object) -> None:
    event = {
        "v": 1,
        "ts": "2026-07-25T12:00:00Z",
        "session": "session-1",
        "seq": 1,
        "type": "decision",
        "actor": "agent",
        "data": {},
    }
    event[field] = value
    with pytest.raises(EventValidationError):
        validate_event(event)


def test_append_event_assigns_sequence_and_jsonl(tmp_path: Path) -> None:
    first = append_event(
        tmp_path, session="safe-session", event_type="session_started", data={}
    )
    second = append_event(
        tmp_path, session="safe-session", event_type="decision", data={"safe": True}
    )
    assert (first["seq"], second["seq"]) == (1, 2)
    assert read_events(tmp_path / "events" / "safe-session.jsonl") == [first, second]


def test_read_events_rejects_sequence_gap(tmp_path: Path) -> None:
    path = tmp_path / "events.jsonl"
    path.write_text(
        '{"actor":"agent","data":{},"seq":2,"session":"s","ts":"2026-07-25T12:00:00Z","type":"decision","v":1}\n',
        encoding="utf-8",
    )
    with pytest.raises(EventValidationError, match="expected seq 1"):
        read_events(path)


@pytest.mark.parametrize(
    "ticket",
    [
        {**TICKET, "quantity": None},
        {**TICKET, "notional": "100.00"},
        {**TICKET, "symbol": "vti"},
        {**TICKET, "limit_price": None},
        {**TICKET, "quantity": 5},
        {**TICKET, "extra": "field"},
    ],
)
def test_ticket_schema_rejects_ambiguous_or_unsafe_terms(ticket: dict) -> None:
    with pytest.raises(OrderValidationError):
        validate_ticket(ticket)


def test_order_legal_lifecycle_requires_exact_confirmation(tmp_path: Path) -> None:
    path, draft = create_order(
        tmp_path,
        session="order-session",
        ticket=TICKET,
        timestamp="2026-07-25T12:00:00Z",
    )
    confirmed = transition_order(
        path,
        to_state="confirmed",
        session="order-session",
        timestamp="2026-07-25T12:00:01Z",
    )
    assert confirmed["state"] == "confirmed"

    with pytest.raises(OrderValidationError, match="confirmation_received"):
        transition_order(
            path,
            to_state="submitted",
            session="order-session",
            events_path=tmp_path / "events" / "order-session.jsonl",
        )

    append_event(
        tmp_path,
        session="order-session",
        event_type="confirmation_requested",
        data={
            "order_id": draft["id"],
            "ticket_fingerprint": draft["ticket_fingerprint"],
            "terms": TICKET,
        },
    )
    confirmation = append_event(
        tmp_path,
        session="order-session",
        event_type="confirmation_received",
        actor="user",
        data={
            "order_id": draft["id"],
            "ticket_fingerprint": ticket_fingerprint(TICKET),
            "confirmed": True,
        },
    )
    submitted = transition_order(
        path,
        to_state="submitted",
        session="order-session",
        events_path=tmp_path / "events" / "order-session.jsonl",
        timestamp="2026-07-25T12:00:02Z",
    )
    assert submitted["state"] == "submitted"
    assert submitted["history"][-1]["event_seq"] == confirmation["seq"]

    partial = transition_order(
        path,
        to_state="partially_filled",
        session="order-session",
        timestamp="2026-07-25T12:00:03Z",
    )
    filled = transition_order(
        path,
        to_state="filled",
        session="order-session",
        timestamp="2026-07-25T12:00:04Z",
    )
    assert partial["state"] == "partially_filled"
    assert validate_order(filled)["state"] == "filled"


def test_wrong_ticket_confirmation_cannot_submit(tmp_path: Path) -> None:
    path, draft = create_order(tmp_path, session="s", ticket=TICKET)
    transition_order(path, to_state="confirmed", session="s")
    append_event(
        tmp_path,
        session="s",
        event_type="confirmation_received",
        actor="user",
        data={
            "order_id": draft["id"],
            "ticket_fingerprint": "0" * 64,
            "confirmed": True,
        },
    )
    with pytest.raises(OrderValidationError, match="exact ticket"):
        transition_order(
            path,
            to_state="submitted",
            session="s",
            events_path=tmp_path / "events" / "s.jsonl",
        )


def test_confirmation_without_matching_request_cannot_submit(tmp_path: Path) -> None:
    path, draft = create_order(tmp_path, session="s", ticket=TICKET)
    transition_order(path, to_state="confirmed", session="s")
    append_event(
        tmp_path,
        session="s",
        event_type="confirmation_received",
        actor="user",
        data={
            "order_id": draft["id"],
            "ticket_fingerprint": draft["ticket_fingerprint"],
            "confirmed": True,
        },
    )
    with pytest.raises(OrderValidationError, match="exact ticket"):
        transition_order(
            path,
            to_state="submitted",
            session="s",
            events_path=tmp_path / "events" / "s.jsonl",
        )


@pytest.mark.parametrize("terminal", ["filled", "canceled", "rejected"])
def test_submitted_order_accepts_broker_terminal_states(
    tmp_path: Path, terminal: str
) -> None:
    path, record = create_order(tmp_path, session="s", ticket=TICKET)
    raw = json.loads(path.read_text())
    raw["state"] = "submitted"
    raw["history"].extend(
        [
            {
                "at": "2026-07-25T12:00:00Z",
                "from": "draft",
                "to": "confirmed",
                "session": "s",
                "event_seq": 2,
                "note": None,
            },
            {
                "at": "2026-07-25T12:00:01Z",
                "from": "confirmed",
                "to": "submitted",
                "session": "s",
                "event_seq": 2,
                "note": None,
            },
        ]
    )
    raw["updated_at"] = "2026-07-25T12:00:01Z"
    path.write_text(json.dumps(raw))
    assert transition_order(path, to_state=terminal, session="s")["state"] == terminal


def test_order_rejects_invalid_session_and_journal_path(tmp_path: Path) -> None:
    with pytest.raises(OrderValidationError, match="session"):
        create_order(tmp_path, session="../escape", ticket=TICKET)
    with pytest.raises(OrderValidationError, match="memory/journal"):
        create_order(tmp_path, session="s", ticket=TICKET, journal="../../private")


@pytest.mark.parametrize(
    ("start", "target"),
    [
        ("draft", "submitted"),
        ("draft", "filled"),
        ("confirmed", "filled"),
        ("filled", "canceled"),
        ("abandoned", "confirmed"),
    ],
)
def test_illegal_transitions_are_rejected(
    tmp_path: Path, start: str, target: str
) -> None:
    path, _ = create_order(tmp_path, session="s", ticket=TICKET)
    if start == "confirmed":
        transition_order(path, to_state="confirmed", session="s")
    elif start == "abandoned":
        transition_order(path, to_state="abandoned", session="s")
    elif start == "filled":
        record = json.loads(path.read_text())
        record["state"] = "filled"
        record["history"].append(
            {
                "at": "2026-07-25T12:00:00Z",
                "from": "draft",
                "to": "filled",
                "session": "s",
                "event_seq": None,
                "note": None,
            }
        )
        path.write_text(json.dumps(record))
        with pytest.raises(OrderValidationError):
            transition_order(path, to_state=target, session="s")
        return
    with pytest.raises(OrderValidationError):
        transition_order(path, to_state=target, session="s")


def test_snapshot_rejects_unknown_and_duplicate_positions() -> None:
    snapshot = {
        "v": 1,
        "ts": "2026-07-25T12:00:00Z",
        "session": "review",
        "source": "robinhood-trading-mcp",
        "balances": {"cash": "100.00"},
        "positions": [
            {
                "symbol": "VTI",
                "quantity": "1",
                "average_cost": "250",
                "mark": "260",
            },
            {
                "symbol": "VTI",
                "quantity": "2",
                "average_cost": "250",
                "mark": "260",
            },
        ],
    }
    with pytest.raises(SnapshotValidationError, match="duplicate"):
        validate_snapshot(snapshot)


def test_normalized_synthetic_snapshot_is_valid() -> None:
    snapshot = {
        "v": 1,
        "ts": "2026-07-25T12:00:00Z",
        "session": "synthetic-review",
        "source": "robinhood-trading-mcp",
        "balances": {"cash": "100.00", "buying_power": "100.00"},
        "positions": [
            {
                "symbol": "VTI",
                "quantity": "1",
                "average_cost": "250",
                "mark": "260",
            }
        ],
    }
    assert validate_snapshot(snapshot)["session"] == "synthetic-review"


def test_cli_log_is_offline_and_writes_valid_event(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "cream_agent.cli.main",
            "log",
            "--memory-root",
            str(tmp_path),
            "--session",
            "cli-session",
            "--type",
            "decision",
            "--data",
            '{"reason":"offline test"}',
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    assert json.loads(result.stdout)["seq"] == 1
    assert read_events(tmp_path / "events" / "cli-session.jsonl")[0]["data"] == {
        "reason": "offline test"
    }
