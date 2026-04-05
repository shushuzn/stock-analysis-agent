"""SQLite-based analysis history persistence."""

from __future__ import annotations

import sqlite3
import json
import time
from pathlib import Path
from typing import Any

DB_PATH = Path.home() / ".stock-analysis-agent" / "history.db"


def _get_conn() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS analyses (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp   REAL,
            stock_symbol TEXT,
            query       TEXT,
            period      TEXT,
            mode        TEXT,
            signal      TEXT,
            report      TEXT,
            tool_results TEXT,
            success     INTEGER
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_symbol ON analyses(stock_symbol)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON analyses(timestamp)")
    conn.commit()
    return conn


def store_analysis(
    symbol: str,
    query: str,
    period: str,
    mode: str,
    signal: str | None,
    report: str,
    tool_results: list[dict[str, Any]],
    success: bool,
) -> int:
    """Store an analysis result. Returns the row id."""
    conn = _get_conn()
    try:
        cursor = conn.execute(
            """
            INSERT INTO analyses (timestamp, stock_symbol, query, period, mode, signal, report, tool_results, success)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                time.time(),
                symbol,
                query,
                period,
                mode,
                signal,
                report,
                json.dumps(tool_results, ensure_ascii=False),
                int(success),
            ),
        )
        conn.commit()
        return cursor.lastrowid or 0
    finally:
        conn.close()


def get_history(symbol: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    """Fetch recent analyses, optionally filtered by symbol."""
    conn = _get_conn()
    try:
        if symbol:
            rows = conn.execute(
                "SELECT * FROM analyses WHERE stock_symbol=? ORDER BY timestamp DESC LIMIT ?",
                (symbol, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM analyses ORDER BY timestamp DESC LIMIT ?",
                (limit,),
            ).fetchall()
        cols = ["id","timestamp","stock_symbol","query","period","mode","signal","report","tool_results","success"]
        results = []
        for row in rows:
            r = dict(zip(cols, row))
            r["symbol"] = r.pop("stock_symbol")
            r["success"] = bool(r["success"])
            try:
                r["tool_results"] = json.loads(r["tool_results"])
            except Exception:
                r["tool_results"] = []
            results.append(r)
        return results
    finally:
        conn.close()


def get_stats(symbol: str | None = None) -> dict[str, Any]:
    """Get aggregate stats for a symbol (or all symbols)."""
    conn = _get_conn()
    try:
        where = "WHERE stock_symbol=?" if symbol else ""
        params = (symbol,) if symbol else ()
        total = conn.execute(
            f"SELECT COUNT(*), SUM(success), COUNT(DISTINCT stock_symbol) FROM analyses {where}",
            params,
        ).fetchone()
        signal_dist = conn.execute(
            f"SELECT signal, COUNT(*) FROM analyses {where} GROUP BY signal",
            params,
        ).fetchall()
        return {
            "total": total[0] or 0,
            "success": total[1] or 0,
            "unique_symbols": total[2] or 0,
            "signal_distribution": dict(signal_dist),
        }
    finally:
        conn.close()
