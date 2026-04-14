"""SQLite-based MACD crossover event persistence."""

from __future__ import annotations

import sqlite3
import time
from pathlib import Path
from typing import Any

DB_PATH = Path.home() / ".stock-analysis-agent" / "macd_events.db"


def _get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS macd_events (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   REAL,
            stock_symbol TEXT,
            event_date  TEXT,
            cross_type  TEXT,
            macd        REAL,
            signal      REAL,
            histogram   REAL,
            period      TEXT
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_macd_symbol ON macd_events(stock_symbol)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_macd_timestamp ON macd_events(timestamp)")
    conn.commit()
    return conn


def store_events(symbol: str, period: str, events: list[dict[str, Any]]) -> int:
    """Store MACD crossover events. Returns count of stored events."""
    if not events:
        return 0
    conn = _get_conn()
    try:
        rows = [
            (
                time.time(),
                symbol,
                e.get("date", ""),
                e.get("type", ""),
                e.get("macd"),
                e.get("signal"),
                e.get("histogram"),
                period,
            )
            for e in events
        ]
        conn.executemany(
            "INSERT INTO macd_events (timestamp, stock_symbol, event_date, cross_type, macd, signal, histogram, period) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            rows,
        )
        conn.commit()
        return len(rows)
    finally:
        conn.close()


def get_events(symbol: str | None = None, limit: int = 100) -> list[dict[str, Any]]:
    """Fetch MACD events, optionally filtered by symbol."""
    conn = _get_conn()
    try:
        if symbol:
            rows = conn.execute(
                "SELECT * FROM macd_events WHERE stock_symbol=? ORDER BY timestamp DESC LIMIT ?",
                (symbol, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM macd_events ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()
        cols = ["id", "timestamp", "stock_symbol", "event_date", "cross_type", "macd", "signal", "histogram", "period"]
        results = []
        for row in rows:
            r = dict(zip(cols, row))
            r["symbol"] = r.pop("stock_symbol")
            results.append(r)
        return results
    finally:
        conn.close()


def get_stats(symbol: str | None = None) -> dict[str, Any]:
    """Get aggregate MACD event stats for a symbol (or all)."""
    conn = _get_conn()
    try:
        where = "WHERE stock_symbol=?" if symbol else ""
        params = (symbol,) if symbol else ()

        total = conn.execute(
            f"SELECT COUNT(*) FROM macd_events {where}", params
        ).fetchone()[0] or 0

        golden = conn.execute(
            f"SELECT COUNT(*) FROM macd_events WHERE cross_type='golden_cross' {where}", params
        ).fetchone()[0] or 0

        death = conn.execute(
            f"SELECT COUNT(*) FROM macd_events WHERE cross_type='death_cross' {where}", params
        ).fetchone()[0] or 0

        by_symbol_rows = conn.execute(
            f"SELECT stock_symbol, COUNT(*) FROM macd_events {where} GROUP BY stock_symbol",
            params,
        ).fetchall()

        return {
            "total": total,
            "golden_cross": golden,
            "death_cross": death,
            "by_symbol": dict(by_symbol_rows),
        }
    finally:
        conn.close()
