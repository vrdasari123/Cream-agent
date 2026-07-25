"""File-backed order records with an explicit safety-gated state machine."""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from decimal import Decimal, InvalidOperation
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

from .common import atomic_write_json, canonical_json, exclusive_lock, parse_timestamp, utc_now
from .events import SESSION_PATTERN, read_events

ORDER_VERSION = 1
ORDER_STATES = frozenset(
    {
        "draft",
        "confirmed",
        "submitted",
        "partially_filled",
        "filled",
        "canceled",
        "rejected",
        "abandoned",
    }
)
TERMINAL_STATES = frozenset({"filled", "canceled", "rejected", "abandoned"})
TRANSITIONS = {
    "draft": frozenset({"confirmed", "abandoned"}),
    "confirmed": frozenset({"submitted", "abandoned"}),
    "submitted": frozenset({"partially_filled", "filled", "canceled", "rejected"}),
    "partially_filled": frozenset(
        {"partially_filled", "filled", "canceled", "rejected"}
    ),
    "filled": frozenset(),
    "canceled": frozenset(),
    "rejected": frozenset(),
    "abandoned": frozenset(),
}
SIDES = frozenset({"buy", "sell"})
ORDER_TYPES = frozenset({"market", "limit", "stop", "stop_limit"})
ORDER_ID_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}-[A-Z][A-Z0-9.-]{0,15}-(buy|sell)-\d{3}$"
)
SYMBOL_PATTERN = re.compile(r"^[A-Z][A-Z0-9.-]{0,15}$")
TICKET_KEYS = frozenset(
    {
        "symbol",
        "side",
        "quantity",
        "notional",
        "order_type",
        "limit_price",
        "stop_price",
        "time_in_force",
    }
)
RECORD_KEYS = frozenset(
    {
        "v",
        "id",
        "created_at",
        "updated_at",
        "session",
        "journal",
        "ticket",
        "ticket_fingerprint",
        "state",
        "history",
    }
)


class OrderValidationError(ValueError):
    """Raised when an order record or transition is invalid."""


def _positive_decimal(value: Any, field: str) -> None:
    if not isinstance(value, str):
        raise OrderValidationError(f"{field} must be a positive decimal string")
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise OrderValidationError(f"{field} must be a positive decimal string") from exc
    if not parsed.is_finite() or parsed <= 0:
        raise OrderValidationError(f"{field} must be a positive decimal string")


def validate_ticket(ticket: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(ticket, Mapping):
        raise OrderValidationError("ticket must be a JSON object")
    unknown = set(ticket) - TICKET_KEYS
    if unknown:
        raise OrderValidationError(f"unknown ticket fields: {', '.join(sorted(unknown))}")
    required = {"symbol", "side", "order_type", "time_in_force"}
    missing = required - set(ticket)
    if missing:
        raise OrderValidationError(f"missing ticket fields: {', '.join(sorted(missing))}")
    normalized = dict(ticket)
    if not isinstance(ticket["symbol"], str) or not SYMBOL_PATTERN.fullmatch(
        ticket["symbol"]
    ):
        raise OrderValidationError("symbol must be an uppercase ticker")
    if ticket["side"] not in SIDES:
        raise OrderValidationError("side must be buy or sell")
    if ticket["order_type"] not in ORDER_TYPES:
        raise OrderValidationError(
            "order_type must be market, limit, stop, or stop_limit"
        )
    if not isinstance(ticket["time_in_force"], str) or not ticket["time_in_force"]:
        raise OrderValidationError("time_in_force must be a non-empty string")
    has_quantity = ticket.get("quantity") is not None
    has_notional = ticket.get("notional") is not None
    if has_quantity == has_notional:
        raise OrderValidationError("ticket requires exactly one of quantity or notional")
    _positive_decimal(
        ticket["quantity"] if has_quantity else ticket["notional"],
        "quantity" if has_quantity else "notional",
    )
    requires_limit = ticket["order_type"] in {"limit", "stop_limit"}
    requires_stop = ticket["order_type"] in {"stop", "stop_limit"}
    if requires_limit != (ticket.get("limit_price") is not None):
        raise OrderValidationError(
            "limit_price is required only for limit and stop_limit orders"
        )
    if requires_stop != (ticket.get("stop_price") is not None):
        raise OrderValidationError(
            "stop_price is required only for stop and stop_limit orders"
        )
    if requires_limit:
        _positive_decimal(ticket["limit_price"], "limit_price")
    if requires_stop:
        _positive_decimal(ticket["stop_price"], "stop_price")
    return normalized


def ticket_fingerprint(ticket: Mapping[str, Any]) -> str:
    normalized = validate_ticket(ticket)
    return hashlib.sha256(canonical_json(normalized).encode()).hexdigest()


def validate_order(record: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(record, Mapping):
        raise OrderValidationError("order record must be a JSON object")
    missing = RECORD_KEYS - set(record)
    unknown = set(record) - RECORD_KEYS
    if missing:
        raise OrderValidationError(f"missing order fields: {', '.join(sorted(missing))}")
    if unknown:
        raise OrderValidationError(f"unknown order fields: {', '.join(sorted(unknown))}")
    if record["v"] != ORDER_VERSION:
        raise OrderValidationError(f"v must be {ORDER_VERSION}")
    if not isinstance(record["id"], str) or not ORDER_ID_PATTERN.fullmatch(record["id"]):
        raise OrderValidationError("id must match YYYY-MM-DD-SYMBOL-side-NNN")
    try:
        parse_timestamp(record["created_at"], "created_at")
        parse_timestamp(record["updated_at"], "updated_at")
    except ValueError as exc:
        raise OrderValidationError(str(exc)) from exc
    if not isinstance(record["session"], str) or not record["session"]:
        raise OrderValidationError("session must be non-empty")
    if record["journal"] is not None and not isinstance(record["journal"], str):
        raise OrderValidationError("journal must be a string path or null")
    ticket = validate_ticket(record["ticket"])
    if record["ticket_fingerprint"] != ticket_fingerprint(ticket):
        raise OrderValidationError("ticket_fingerprint does not match ticket")
    if record["state"] not in ORDER_STATES:
        raise OrderValidationError(f"unsupported order state: {record['state']!r}")
    history = record["history"]
    if not isinstance(history, list) or not history:
        raise OrderValidationError("history must be a non-empty array")
    current = None
    for index, entry in enumerate(history):
        if not isinstance(entry, dict):
            raise OrderValidationError(f"history[{index}] must be an object")
        expected_keys = {"at", "from", "to", "session", "event_seq", "note"}
        if set(entry) != expected_keys:
            raise OrderValidationError(f"history[{index}] has invalid fields")
        try:
            parse_timestamp(entry["at"], f"history[{index}].at")
        except ValueError as exc:
            raise OrderValidationError(str(exc)) from exc
        if index == 0:
            if entry["from"] is not None or entry["to"] != "draft":
                raise OrderValidationError("history must begin with creation into draft")
        else:
            if entry["from"] != current or entry["to"] not in TRANSITIONS[current]:
                raise OrderValidationError(
                    f"illegal history transition {entry['from']!r} -> {entry['to']!r}"
                )
        if not isinstance(entry["session"], str) or not entry["session"]:
            raise OrderValidationError(f"history[{index}].session must be non-empty")
        if entry["event_seq"] is not None and (
            not isinstance(entry["event_seq"], int)
            or isinstance(entry["event_seq"], bool)
            or entry["event_seq"] < 1
        ):
            raise OrderValidationError(
                f"history[{index}].event_seq must be a positive integer or null"
            )
        if entry["note"] is not None and not isinstance(entry["note"], str):
            raise OrderValidationError(f"history[{index}].note must be a string or null")
        current = entry["to"]
    if record["state"] != current:
        raise OrderValidationError("state must match the final history entry")
    return dict(record)


def _next_order_id(orders_dir: Path, ticket: Mapping[str, Any], day: date) -> str:
    prefix = f"{day.isoformat()}-{ticket['symbol']}-{ticket['side']}-"
    used = {
        int(path.stem[-3:])
        for path in orders_dir.glob(f"{prefix}[0-9][0-9][0-9].json")
        if ORDER_ID_PATTERN.fullmatch(path.stem)
    }
    for number in range(1, 1000):
        if number not in used:
            return f"{prefix}{number:03d}"
    raise OrderValidationError("daily order ID space exhausted")


def create_order(
    memory_root: Path | str,
    *,
    session: str,
    ticket: Mapping[str, Any],
    journal: str | None = None,
    timestamp: str | None = None,
) -> tuple[Path, dict[str, Any]]:
    normalized = validate_ticket(ticket)
    if not isinstance(session, str) or not SESSION_PATTERN.fullmatch(session):
        raise OrderValidationError("session must be a safe 1-128 character identifier")
    if journal is not None:
        journal_path = PurePosixPath(journal)
        if (
            journal_path.is_absolute()
            or journal_path.parts[:2] != ("memory", "journal")
            or ".." in journal_path.parts
        ):
            raise OrderValidationError(
                "journal must be a relative path under memory/journal/"
            )
    orders_dir = Path(memory_root) / "orders"
    orders_dir.mkdir(parents=True, exist_ok=True)
    at = timestamp or utc_now()
    try:
        parse_timestamp(at, "timestamp")
    except ValueError as exc:
        raise OrderValidationError(str(exc)) from exc
    lock_path = orders_dir / ".orders.lock"
    with exclusive_lock(lock_path):
        order_id = _next_order_id(orders_dir, normalized, date.fromisoformat(at[:10]))
        record = {
            "v": ORDER_VERSION,
            "id": order_id,
            "created_at": at,
            "updated_at": at,
            "session": session,
            "journal": journal,
            "ticket": normalized,
            "ticket_fingerprint": ticket_fingerprint(normalized),
            "state": "draft",
            "history": [
                {
                    "at": at,
                    "from": None,
                    "to": "draft",
                    "session": session,
                    "event_seq": None,
                    "note": "Draft ticket created; no order submitted.",
                }
            ],
        }
        validate_order(record)
        path = orders_dir / f"{order_id}.json"
        atomic_write_json(path, record)
    return path, record


def _matching_confirmation(
    events_path: Path,
    *,
    session: str,
    order_id: str,
    fingerprint: str,
) -> dict[str, Any] | None:
    requested = False
    matches: list[dict[str, Any]] = []
    for event in read_events(events_path):
        data = event["data"]
        same_ticket = (
            event["session"] == session
            and data.get("order_id") == order_id
            and data.get("ticket_fingerprint") == fingerprint
        )
        if event["type"] == "confirmation_requested" and same_ticket:
            try:
                requested = ticket_fingerprint(data.get("terms")) == fingerprint
            except OrderValidationError:
                requested = False
        elif (
            event["type"] == "confirmation_received"
            and same_ticket
            and requested
            and event["actor"] == "user"
            and data.get("confirmed") is True
        ):
            matches.append(event)
            requested = False
        elif event["type"] == "confirmation_received" and same_ticket:
            requested = False
    return matches[-1] if matches else None


def transition_order(
    path: Path | str,
    *,
    to_state: str,
    session: str,
    events_path: Path | str | None = None,
    event_seq: int | None = None,
    note: str | None = None,
    timestamp: str | None = None,
) -> dict[str, Any]:
    order_path = Path(path)
    lock_path = order_path.with_suffix(order_path.suffix + ".lock")
    with exclusive_lock(lock_path):
        try:
            record = json.loads(order_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise OrderValidationError(f"cannot read order record: {exc}") from exc
        validate_order(record)
        current = record["state"]
        if to_state not in ORDER_STATES:
            raise OrderValidationError(f"unsupported order state: {to_state!r}")
        if to_state not in TRANSITIONS[current]:
            raise OrderValidationError(
                f"illegal order transition {current!r} -> {to_state!r}"
            )
        if to_state == "submitted":
            if events_path is None:
                raise OrderValidationError(
                    "submission requires the session event log"
                )
            confirmation = _matching_confirmation(
                Path(events_path),
                session=session,
                order_id=record["id"],
                fingerprint=record["ticket_fingerprint"],
            )
            if confirmation is None:
                raise OrderValidationError(
                    "submission requires a matching confirmation_received event "
                    "for the exact ticket"
                )
            event_seq = confirmation["seq"]
        at = timestamp or utc_now()
        record["state"] = to_state
        record["updated_at"] = at
        record["history"].append(
            {
                "at": at,
                "from": current,
                "to": to_state,
                "session": session,
                "event_seq": event_seq,
                "note": note,
            }
        )
        validate_order(record)
        atomic_write_json(order_path, record)
        return record
