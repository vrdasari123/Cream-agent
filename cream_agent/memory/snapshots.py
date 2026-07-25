"""Minimal normalized snapshot envelope for fixtures and future P/L helpers."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any, Mapping

from .common import parse_timestamp
from .orders import SYMBOL_PATTERN

SNAPSHOT_VERSION = 1
SNAPSHOT_KEYS = frozenset(
    {"v", "ts", "session", "source", "balances", "positions"}
)
BALANCE_KEYS = frozenset({"cash", "buying_power", "total_equity"})
POSITION_KEYS = frozenset({"symbol", "quantity", "average_cost", "mark"})


class SnapshotValidationError(ValueError):
    """Raised when a normalized account snapshot is structurally invalid."""


def _decimal(value: Any, field: str, *, positive: bool = False) -> None:
    if not isinstance(value, str):
        raise SnapshotValidationError(f"{field} must be a decimal string")
    try:
        parsed = Decimal(value)
    except InvalidOperation as exc:
        raise SnapshotValidationError(f"{field} must be a decimal string") from exc
    if not parsed.is_finite() or (positive and parsed <= 0):
        raise SnapshotValidationError(f"{field} must be a valid decimal string")


def validate_snapshot(snapshot: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(snapshot, Mapping):
        raise SnapshotValidationError("snapshot must be a JSON object")
    missing = SNAPSHOT_KEYS - set(snapshot)
    unknown = set(snapshot) - SNAPSHOT_KEYS
    if missing:
        raise SnapshotValidationError(
            f"missing snapshot fields: {', '.join(sorted(missing))}"
        )
    if unknown:
        raise SnapshotValidationError(
            f"unknown snapshot fields: {', '.join(sorted(unknown))}"
        )
    if snapshot["v"] != SNAPSHOT_VERSION:
        raise SnapshotValidationError(f"v must be {SNAPSHOT_VERSION}")
    try:
        parse_timestamp(snapshot["ts"], "ts")
    except ValueError as exc:
        raise SnapshotValidationError(str(exc)) from exc
    if not isinstance(snapshot["session"], str) or not snapshot["session"]:
        raise SnapshotValidationError("session must be non-empty")
    if snapshot["source"] != "robinhood-trading-mcp":
        raise SnapshotValidationError("source must be robinhood-trading-mcp")
    balances = snapshot["balances"]
    if not isinstance(balances, dict) or not balances:
        raise SnapshotValidationError("balances must be a non-empty object")
    if set(balances) - BALANCE_KEYS:
        raise SnapshotValidationError("balances contains unsupported fields")
    for key, value in balances.items():
        _decimal(value, f"balances.{key}")
    positions = snapshot["positions"]
    if not isinstance(positions, list):
        raise SnapshotValidationError("positions must be an array")
    seen: set[str] = set()
    for index, position in enumerate(positions):
        if not isinstance(position, dict) or set(position) != POSITION_KEYS:
            raise SnapshotValidationError(
                f"positions[{index}] must contain symbol, quantity, average_cost, and mark"
            )
        symbol = position["symbol"]
        if not isinstance(symbol, str) or not SYMBOL_PATTERN.fullmatch(symbol):
            raise SnapshotValidationError(f"positions[{index}].symbol is invalid")
        if symbol in seen:
            raise SnapshotValidationError(f"duplicate position symbol: {symbol}")
        seen.add(symbol)
        _decimal(position["quantity"], f"positions[{index}].quantity", positive=True)
        for field in ("average_cost", "mark"):
            _decimal(position[field], f"positions[{index}].{field}", positive=True)
    return dict(snapshot)
