"""Virtual portfolio management — track positions, P&L, buy/sell operations."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

DB_PATH = Path.home() / ".stock-analysis-agent" / "portfolio.json"


def _load() -> dict[str, Any]:
    if not DB_PATH.exists():
        return {"positions": {}, "history": []}
    try:
        return json.loads(DB_PATH.read_text())  # type: ignore[no-any-return]
    except Exception:
        return {"positions": {}, "history": []}


def _save(data: dict) -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    DB_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def buy(symbol: str, shares: float, price: float) -> dict[str, Any]:
    """Buy shares at given price. Returns updated position."""
    data = _load()
    cost = shares * price
    if symbol in data["positions"]:
        pos = data["positions"][symbol]
        total_cost = pos["shares"] * pos["avg_cost"] + cost
        pos["shares"] += shares
        pos["avg_cost"] = total_cost / pos["shares"]
    else:
        data["positions"][symbol] = {
            "shares": shares,
            "avg_cost": price,
        }
    data["history"].append({
        "timestamp": time.time(),
        "action": "buy",
        "symbol": symbol,
        "shares": shares,
        "price": price,
        "total": cost,
    })
    _save(data)
    return get_position(symbol)


def sell(symbol: str, shares: float, price: float) -> dict[str, Any]:
    """Sell shares at given price. Returns updated position."""
    data = _load()
    if symbol not in data["positions"]:
        return {"error": f"No position for {symbol}"}
    pos = data["positions"][symbol]
    if shares > pos["shares"]:
        return {"error": f"Insufficient shares: have {pos['shares']}, selling {shares}"}
    proceeds = shares * price
    pos["shares"] -= shares
    if pos["shares"] <= 0:
        del data["positions"][symbol]
    data["history"].append({
        "timestamp": time.time(),
        "action": "sell",
        "symbol": symbol,
        "shares": shares,
        "price": price,
        "total": proceeds,
    })
    _save(data)
    return get_position(symbol)


def get_position(symbol: str) -> dict[str, Any]:
    """Get current position with unrealized P&L (requires current price)."""
    data = _load()
    if symbol not in data["positions"]:
        return {"symbol": symbol, "shares": 0, "avg_cost": 0, "error": None}
    return {"symbol": symbol, **data["positions"][symbol]}


def get_all_positions() -> dict[str, Any]:
    """Get all positions."""
    return _load()["positions"]  # type: ignore[no-any-return]


def get_history(limit: int = 50) -> list[dict]:
    data = _load()
    return data["history"][-limit:]  # type: ignore[no-any-return]


def clear_all() -> None:
    _save({"positions": {}, "history": []})
