"""FastAPI web server for Stock Analysis Agent.

Run with:
    uvicorn src.api:app --reload --port 8000

Endpoints:
    GET  /            — Health check
    GET  /tools       — List available tools
    POST /analyze     — Analyze a stock (streaming or blocking)
    GET  /analyze     — Same as POST (query params)
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, AsyncGenerator

from fastapi import FastAPI, HTTPException, Query, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .agent import ReActAgent, extract_symbol
from .report import format_report
from .tools import list_tools


# ── Request/Response Models ───────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    query: str
    symbol: str | None = None
    period: str = "6mo"
    stream: bool = False


class ToolInfo(BaseModel):
    name: str
    desc: str
    args: dict


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="Stock Analysis Agent API",
    description="ReAct-based AI agent for stock market analysis",
    version="0.1.0",
)


@app.get("/")
async def health():
    return {"status": "ok", "service": "stock-analysis-agent", "version": "0.1.0"}


@app.get("/tools")
async def get_tools():
    """List all available stock analysis tools."""
    return {"tools": list_tools()}


@app.post("/analyze")
async def analyze(req: AnalyzeRequest):
    """Analyze a stock with natural language query."""
    if not req.query:
        raise HTTPException(status_code=400, detail="query is required")

    symbol = req.symbol or extract_symbol(req.query)
    if not symbol:
        raise HTTPException(
            status_code=400,
            detail="Could not detect stock symbol. Please provide it explicitly.",
        )

    if req.stream:
        return StreamingResponse(
            _stream_analysis(req.query, symbol, req.period),
            media_type="text/plain",
            headers={"X-Symbol": symbol},
        )

    # Blocking analysis
    agent = ReActAgent(max_steps=10, verbose=False)
    try:
        results = agent.analyze(req.query, symbol)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    report = format_report(symbol, req.query, results)
    return {
        "symbol": symbol,
        "query": req.query,
        "period": req.period,
        "report": report,
        "tool_results": results,
    }


@app.get("/analyze")
async def analyze_get(
    query: str = Query(..., description="Natural language analysis request"),
    symbol: str | None = Query(None, description="Stock ticker or A-share code"),
    period: str = Query("6mo", description="Historical period: 1mo, 3mo, 6mo, 1y, 2y"),
    stream: bool = Query(False, description="Enable streaming output"),
):
    """GET version of /analyze."""
    req = AnalyzeRequest(query=query, symbol=symbol, period=period, stream=stream)
    return await analyze(req)


# ── Streaming ─────────────────────────────────────────────────────────────────

async def _stream_analysis(query: str, symbol: str, period: str) -> AsyncGenerator[str, None]:
    """Stream analysis results as they are computed."""
    agent = ReActAgent(max_steps=10, verbose=False)

    selected = __import__("src.tools", fromlist=[""]).select_tools_for_task(query, symbol)
    tools_chosen = [t[0] for t in selected]

    yield f"🎯 Analyzing {symbol} with tools: {', '.join(tools_chosen)}\n\n"
    yield f"📡 Using data period: {period}\n\n"

    for i, (tool_name, kwargs) in enumerate(selected):
        step_num = i + 1
        yield f"▶ Step {step_num}/{len(selected)}: Calling {tool_name}({kwargs})\n"

        # Run in executor to not block
        loop = asyncio.get_event_loop()
        try:
            data = await loop.run_in_executor(
                None, lambda: __import__("src.tools", fromlist=[""]).execute_tool(tool_name, **kwargs)
            )
        except Exception as e:
            yield f"   ❌ Error: {e}\n"
            continue

        # Observe
        observation = _make_observation(tool_name, data)
        yield f"   ✅ {observation}\n\n"
        await asyncio.sleep(0.05)  # Small delay for streaming feel

    # Final report
    yield "─" * 50 + "\n"
    yield "📊 Final Report:\n\n"

    try:
        results = agent.history
        if not results:
            results = agent.analyze(query, symbol)
        report = format_report(symbol, query, results)
    except Exception as e:
        report = f"Error generating report: {e}"

    for line in report.split("\n"):
        yield line + "\n"
        await asyncio.sleep(0.02)


def _make_observation(tool: str, data: Any) -> str:
    if isinstance(data, dict) and "error" in data:
        return f"Error: {data['error']}"
    if not isinstance(data, dict):
        return str(data)[:100]

    if tool == "get_quote":
        return f"Price: ${data.get('price', 'N/A')}, Change: {data.get('change_pct', 'N/A')}%"
    elif tool == "get_a_share_quote":
        return f"Price: ¥{data.get('price', 'N/A')}, Change: {data.get('change_pct', 'N/A')}%"
    elif tool == "calc_rsi":
        val = data.get("current", "N/A")
        sig = data.get("signal", "")
        return f"RSI={val} ({sig})"
    elif tool == "calc_macd":
        h = data.get("current", {}).get("histogram", "?")
        return f"MACD Histogram={h}"
    elif tool == "calc_all":
        rsi = data.get("rsi", {}).get("value", "?")
        macd = data.get("macd", {}).get("histogram", "?")
        return f"RSI={rsi}, MACD Hist={macd}"
    elif tool == "get_fundamentals":
        pe = data.get("pe_ratio") or data.get("pe", "?")
        return f"P/E={pe}"
    else:
        keys = list(data.keys())[:3]
        return f"Fields: {keys}"
