"""Watchlist management with price alerts."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any

DB_PATH = Path.home() / ".stock-analysis-agent" / "watchlist.json"


def _load() -> dict[str, Any]:
    if not DB_PATH.exists():
        return {"symbols": [], "alerts": {}}
    try:
        return json.loads(DB_PATH.read_text())
    except Exception:
        return {"symbols": [], "alerts": {}}


def _save(data: dict) -> None:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    DB_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def add(symbol: str) -> dict[str, Any]:
    data = _load()
    sym = symbol.strip().upper()
    if sym not in data["symbols"]:
        data["symbols"].append(sym)
    _save(data)
    return get_all()


def remove(symbol: str) -> dict[str, Any]:
    data = _load()
    sym = symbol.strip().upper()
    data["symbols"] = [s for s in data["symbols"] if s != sym]
    if sym in data["alerts"]:
        del data["alerts"][sym]
    _save(data)
    return get_all()


def set_alert(symbol: str, above: float | None = None, below: float | None = None, rsi_threshold: float | None = None) -> dict[str, Any]:
    data = _load()
    sym = symbol.strip().upper()
    if sym not in data["symbols"]:
        data["symbols"].append(sym)
    existing = data["alerts"].get(sym, {})
    data["alerts"][sym] = {
        "above": above,
        "below": below,
        "rsi_threshold": rsi_threshold if rsi_threshold is not None else existing.get("rsi_threshold"),
        "last_triggered": existing.get("last_triggered"),
    }
    _save(data)
    return get_all()


def get_all() -> dict[str, Any]:
    return _load()


def check_alerts(prices: dict[str, float]) -> list[dict[str, Any]]:
    """Check which alerts are triggered by current prices."""
    data = _load()
    triggered = []
    for sym, price in prices.items():
        if sym not in data["alerts"]:
            continue
        alert = data["alerts"][sym]
        above = alert.get("above")
        below = alert.get("below")
        hit = False
        reason = ""
        if above is not None and price >= above:
            hit, reason = True, f"价格突破 ¥{above}（当前 ¥{price}）"
        elif below is not None and price <= below:
            hit, reason = True, f"价格跌破 ¥{below}（当前 ¥{price}）"
        if hit:
            last = alert.get("last_triggered", 0)
            if time.time() - last > 3600:  # min 1h between same alerts
                data["alerts"][sym]["last_triggered"] = time.time()
                triggered.append({"symbol": sym, "price": price, "reason": reason})
    if triggered:
        _save(data)
    return triggered
