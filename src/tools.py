"""Tool registry and executor for stock analysis agent.

Provides a unified interface to all stock analysis tools,
wrapping the stock-analysis-mcp tool functions directly.
"""

from __future__ import annotations

import json
from typing import Any, Callable, Literal

# Import from stock-analysis-mcp (sibling project)
import sys
from pathlib import Path

# Add stock-analysis-mcp to path
_mcp_path = Path(__file__).parent.parent.parent / "stock-analysis-mcp" / "src"
sys.path.insert(0, str(_mcp_path))

from tools import market, technical, screener, analyzer  # noqa: E402
from tools.china import get_a_share_quote  # noqa: E402


def _call(fn: Callable, **kwargs) -> dict[str, Any]:
    """Call a tool function and parse JSON result."""
    raw = fn(**kwargs)
    try:
        return json.loads(raw)
    except Exception:
        return {"raw": raw}


# ── Tool Registry ─────────────────────────────────────────────────────────────

TOOLS: dict[str, dict] = {
    "get_quote": {
        "fn": lambda symbol: _call(market.get_quote, symbol=symbol),
        "desc": "Get real-time US stock quote (price, OHLC, volume)",
        "args": {"symbol": "str - US ticker, e.g. AAPL, NVDA"},
    },
    "get_a_share_quote": {
        "fn": lambda symbol: _call(get_a_share_quote, symbol=symbol),
        "desc": "Get real-time China A-share quote",
        "args": {"symbol": "str - A-share code, e.g. 600519, 000001"},
    },
    "calc_rsi": {
        "fn": lambda symbol, period="6mo": _call(technical.calc_rsi, symbol=symbol, period=period),
        "desc": "Calculate RSI (Relative Strength Index)",
        "args": {"symbol": "str", "period": "str - 1mo, 3mo, 6mo, 1y (default 6mo)"},
    },
    "calc_macd": {
        "fn": lambda symbol, period="6mo": _call(technical.calc_macd, symbol=symbol, period=period),
        "desc": "Calculate MACD (Moving Average Convergence Divergence)",
        "args": {"symbol": "str", "period": "str"},
    },
    "calc_bollinger": {
        "fn": lambda symbol, period="6mo": _call(technical.calc_bollinger, symbol=symbol, period=period),
        "desc": "Calculate Bollinger Bands",
        "args": {"symbol": "str", "period": "str"},
    },
    "calc_kdj": {
        "fn": lambda symbol, period="6mo": _call(technical.calc_kdj, symbol=symbol, period=period),
        "desc": "Calculate KDJ indicator (Chinese markets)",
        "args": {"symbol": "str", "period": "str"},
    },
    "calc_atr": {
        "fn": lambda symbol, period="6mo": _call(technical.calc_atr, symbol=symbol, period=period),
        "desc": "Calculate ATR (Average True Range) for volatility",
        "args": {"symbol": "str", "period": "str"},
    },
    "calc_all": {
        "fn": lambda symbol, period="6mo": _call(technical.calc_all, symbol=symbol, period=period),
        "desc": "Calculate all technical indicators at once (RSI, MACD, Bollinger, KDJ, ATR)",
        "args": {"symbol": "str", "period": "str"},
    },
    "get_fundamentals": {
        "fn": lambda symbol: _call(market.get_fundamentals, symbol=symbol),
        "desc": "Get fundamental data (P/E, EPS, market cap, ROE, dividend)",
        "args": {"symbol": "str - stock ticker"},
    },
    "analyze_trend": {
        "fn": lambda symbol, period="6mo": _call(analyzer.analyze_trend, symbol=symbol, period=period),
        "desc": "Analyze trend using MA crossovers (MA5/MA10/MA20/MA60)",
        "args": {"symbol": "str", "period": "str"},
    },
    "compare_stocks": {
        "fn": lambda symbols, period="6mo": _call(analyzer.compare_stocks, symbols=",".join(symbols) if isinstance(symbols, list) else symbols, period=period),
        "desc": "Compare multiple stocks (Sharpe ratio, max drawdown, volatility)",
        "args": {"symbols": "list[str]", "period": "str"},
    },
    "get_summary": {
        "fn": lambda symbol, period="6mo": _call(analyzer.get_summary, symbol=symbol, period=period),
        "desc": "Full stock report: quote + fundamentals + all indicators",
        "args": {"symbol": "str", "period": "str"},
    },
}


def list_tools() -> list[dict]:
    """Return all available tools with descriptions."""
    return [
        {"name": name, "desc": info["desc"], "args": info["args"]}
        for name, info in TOOLS.items()
    ]


def execute_tool(name: str, **kwargs) -> dict[str, Any]:
    """Execute a tool by name, return parsed result."""
    if name not in TOOLS:
        return {"error": f"Unknown tool: {name}"}
    return TOOLS[name]["fn"](**kwargs)


# ── Tool Selection Strategy ───────────────────────────────────────────────────

def select_tools_for_task(task: str, symbol: str) -> list[tuple[str, dict]]:
    """Given a task description and symbol, select appropriate tools and their args.

    Returns list of (tool_name, kwargs) in execution order.
    """
    task_lower = task.lower()
    selections = []

    # Always get quote first
    if symbol.isdigit() and len(symbol) == 6:
        selections.append(("get_a_share_quote", {"symbol": symbol}))
    else:
        selections.append(("get_quote", {"symbol": symbol}))

    # Fundamentals for investment analysis
    if any(kw in task_lower for kw in ["基本面", "估值", "财务", "fundamental", "invest", "分析", "报告"]):
        selections.append(("get_fundamentals", {"symbol": symbol}))

    # Technical indicators for trend/volatility analysis
    if any(kw in task_lower for kw in ["技术", "趋势", "指标", "technical", "trend", "rsi", "macd", "波动"]):
        selections.append(("calc_all", {"symbol": symbol}))

    # Specific indicators
    if "rsi" in task_lower:
        selections.append(("calc_rsi", {"symbol": symbol}))
    if "macd" in task_lower:
        selections.append(("calc_macd", {"symbol": symbol}))
    if "kdj" in task_lower:
        selections.append(("calc_kdj", {"symbol": symbol}))
    if "atr" in task_lower or "波动" in task_lower:
        selections.append(("calc_atr", {"symbol": symbol}))
    if "布林" in task_lower or "bollinger" in task_lower:
        selections.append(("calc_bollinger", {"symbol": symbol}))

    # Trend analysis
    if any(kw in task_lower for kw in ["趋势", "均线", "ma", "trend", "交叉"]):
        selections.append(("analyze_trend", {"symbol": symbol}))

    # If nothing specific matched, do a full analysis
    if len(selections) == 1:
        selections.append(("calc_all", {"symbol": symbol}))
        selections.append(("get_fundamentals", {"symbol": symbol}))

    return selections
