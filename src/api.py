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
from pathlib import Path
from typing import Any, AsyncGenerator

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from .agent import ReActAgent, extract_symbol
from .report import format_report
from .agent_tools import list_tools, calc_bollinger_squeeze, check_rsi_threshold
from .persistence import store_analysis, get_history, get_stats
from .portfolio import buy, sell, get_all_positions, get_history as get_portfolio_history, clear_all
from .export_pdf import generate_pdf
from .watchlist import add as wl_add, remove as wl_remove, set_alert, get_all as wl_get_all, check_alerts
from .tts import speak, speak_price


# ── Request/Response Models ───────────────────────────────────────────────────

class AnalyzeRequest(BaseModel):
    query: str
    symbol: str | None = None
    period: str = "6mo"
    stream: bool = False
    llm: bool = False  # Enable LLM-powered analysis


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
            _stream_analysis(req.query, symbol, req.period, req.llm),
            media_type="text/plain",
            headers={"X-Symbol": symbol},
        )

    # Blocking analysis
    agent = ReActAgent(max_steps=10, verbose=False)
    try:
        if req.llm:
            # LLM-powered: returns analysis text directly
            result = agent.analyze(req.query, symbol, use_llm=True)
            store_analysis(symbol, req.query, req.period, "llm", None, result, [], True)
            return {
                "symbol": symbol,
                "query": req.query,
                "period": req.period,
                "analysis": result,
                "mode": "llm",
            }
        else:
            results = agent.analyze(req.query, symbol)
            report = format_report(symbol, req.query, results)
            signal = _extract_signal(results)
            store_analysis(symbol, req.query, req.period, "data", signal, report, results, True)
            return {
                "symbol": symbol,
                "query": req.query,
                "period": req.period,
                "report": report,
                "tool_results": results,
                "mode": "data",
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/analyze")
async def analyze_get(
    query: str = Query(..., description="Natural language analysis request"),
    symbol: str | None = Query(None, description="Stock ticker or A-share code"),
    period: str = Query("6mo", description="Historical period: 1mo, 3mo, 6mo, 1y, 2y"),
    stream: bool = Query(False, description="Enable streaming output"),
    llm: bool = Query(False, description="Enable LLM-powered analysis"),
):
    """GET version of /analyze."""
    req = AnalyzeRequest(query=query, symbol=symbol, period=period, stream=stream, llm=llm)
    return await analyze(req)


# ── Streaming ─────────────────────────────────────────────────────────────────

async def _stream_analysis(query: str, symbol: str, period: str, use_llm: bool = False) -> AsyncGenerator[str, None]:
    """Stream analysis results as they are computed."""
    selected = __import__("src.tools", fromlist=[""]).select_tools_for_task(query, symbol)
    tools_chosen = [t[0] for t in selected]

    yield f"🎯 Analyzing {symbol} with tools: {', '.join(tools_chosen)}\n\n"
    yield f"📡 Data period: {period} | Mode: {'🤖 LLM分析' if use_llm else '📊 数据报告'}\n\n"

    # Collect results
    results = []
    for i, (tool_name, kwargs) in enumerate(selected):
        step_num = i + 1
        yield f"▶ Step {step_num}/{len(selected)}: Calling {tool_name}({kwargs})\n"

        loop = asyncio.get_event_loop()
        try:
            data = await loop.run_in_executor(
                None, lambda: __import__("src.tools", fromlist=[""]).execute_tool(tool_name, **kwargs)
            )
        except Exception as e:
            yield f"   ❌ Error: {e}\n"
            continue

        observation = _make_observation(tool_name, data)
        yield f"   ✅ {observation}\n\n"
        await asyncio.sleep(0.05)

    # Final output
    yield "─" * 50 + "\n"

    try:
        if use_llm:
            from .llm import analyze_with_llm_streaming
            yield "🤖 LLM分析中...\n\n"
            async for chunk in analyze_with_llm_streaming(symbol, query, results):
                yield chunk + "\n"
        else:
            report = format_report(symbol, query, results)
            yield "📊 Final Report:\n\n"
            for line in report.split("\n"):
                yield line + "\n"
                await asyncio.sleep(0.02)
    except Exception as e:
        yield f"Error generating report: {e}"


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


# ── History & Stats ─────────────────────────────────────────────────────────────

@app.get("/history")
async def history(symbol: str | None = Query(None), limit: int = Query(50)):
    """Fetch recent analysis history, optionally filtered by symbol."""
    return get_history(symbol=symbol, limit=limit)


@app.get("/stats")
async def stats(symbol: str | None = Query(None)):
    """Get aggregate stats for a symbol or all symbols."""
    return get_stats(symbol=symbol)


# ── Notifications ─────────────────────────────────────────────────────────────

class NotifyRequest(BaseModel):
    sckey: str | None = None
    message: str | None = None


@app.get("/compare")
async def compare(
    symbols: str = Query(..., description="Comma-separated stock symbols"),
    period: str = Query("6mo", description="Historical period"),
):
    """Compare multiple stocks side by side using compare_stocks tool."""
    from .agent_tools import compare_stocks as compare_fn
    return compare_fn(symbols, period)


@app.post("/notify")
async def notify(req: NotifyRequest):
    """Push analysis result via ServerChan (wxpusher/ServerChan).
    If no body provided, reads SCKEY from config file (~/.stock-analysis-agent/config.json).
    """
    import json as json_lib
    from pathlib import Path

    # Load SCKEY from config or body
    sckey = req.sckey
    message = req.message
    if not sckey:
        config_path = Path.home() / ".stock-analysis-agent" / "config.json"
        if config_path.exists():
            try:
                cfg = json_lib.loads(config_path.read_text())
                sckey = cfg.get("serverchan_sckey") or cfg.get("sckey")
            except Exception:
                pass
    if not sckey:
        raise HTTPException(status_code=400, detail="SCKEY required (body or config file)")

    if not message:
        raise HTTPException(status_code=400, detail="message is required")

    try:
        import urllib.request
        import urllib.parse
        url = f"https://wxpusher.zjiecode.com/api/send/message/?appToken={sckey}&content={urllib.parse.quote(message)}&contentType=1"
        req_notify = urllib.request.Request(url, headers={"User-Agent": "StockAnalysisAgent/1.0"})
        with urllib.request.urlopen(req_notify, timeout=10) as resp:
            result = json_lib.loads(resp.read())
            if result.get("code") == 1000:
                return {"success": True, "result": result}
            else:
                return {"success": False, "result": result}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Portfolio ────────────────────────────────────────────────────────────────

class PositionRequest(BaseModel):
    symbol: str
    shares: float
    price: float


@app.post("/portfolio/buy")
async def portfolio_buy(req: PositionRequest):
    return buy(req.symbol, req.shares, req.price)


@app.post("/portfolio/sell")
async def portfolio_sell(req: PositionRequest):
    return sell(req.symbol, req.shares, req.price)


@app.get("/portfolio")
async def portfolio_positions():
    """Get all positions with current prices and unrealized P&L."""
    positions = get_all_positions()
    results = {}
    for symbol in positions:
        from .agent_tools import get_quote
        q = get_quote(symbol)
        if "error" not in q:
            p = positions[symbol]
            current = q.get("price", 0)
            avg = p["avg_cost"]
            results[symbol] = {
                **p,
                "current_price": current,
                "market_value": round(current * p["shares"], 2),
                "unrealized_pnl": round((current - avg) * p["shares"], 2),
                "unrealized_pnl_pct": round((current - avg) / avg * 100, 2) if avg else 0,
            }
        else:
            results[symbol] = {**positions[symbol], "quote_error": q.get("error")}
    return results


@app.get("/portfolio/history")
async def portfolio_history(limit: int = Query(50)):
    return get_portfolio_history(limit=limit)


@app.delete("/portfolio")
async def portfolio_clear():
    clear_all()
    return {"success": True}


# ── Export ─────────────────────────────────────────────────────────────────

@app.get("/export")
async def export_pdf(
    symbol: str = Query(...),
    query: str = Query(""),
):
    """Export analysis report as PDF."""
    try:
        agent = ReActAgent(max_steps=10, verbose=False)
        results = agent.analyze(query, symbol)
        report = format_report(symbol, query, results)
        pdf_bytes = generate_pdf(symbol, query, report, results)
        from fastapi.responses import Response
        return Response(content=pdf_bytes, media_type="application/pdf",
                        headers={"Content-Disposition": f"attachment; filename={symbol}_report.pdf"})
    except ImportError as e:
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Watchlist ────────────────────────────────────────────────────────────────

class WatchlistAlertRequest(BaseModel):
    symbol: str
    above: float | None = None
    below: float | None = None
    rsi_threshold: float | None = None


@app.get("/watchlist")
async def watchlist_get():
    """Get watchlist with current prices."""
    wl = wl_get_all()
    results = {"symbols": wl["symbols"], "alerts": wl["alerts"], "quotes": {}}
    for sym in wl["symbols"]:
        from .agent_tools import get_quote
        q = get_quote(sym)
        if "error" not in q:
            results["quotes"][sym] = {"price": q.get("price"), "change_pct": q.get("change_pct")}
    return results


@app.post("/watchlist")
async def watchlist_add(req: WatchlistAlertRequest):
    return wl_add(req.symbol)


@app.delete("/watchlist/{symbol}")
async def watchlist_remove(symbol: str):
    return wl_remove(symbol)


@app.post("/watchlist/alert")
async def watchlist_set_alert(req: WatchlistAlertRequest):
    return set_alert(req.symbol, req.above, req.below, req.rsi_threshold)


@app.get("/watchlist/check")
async def watchlist_check():
    """Check alerts against current prices, return triggered alerts."""
    wl = wl_get_all()
    prices = {}
    for sym in wl["symbols"]:
        from .agent_tools import get_quote
        q = get_quote(sym)
        if "error" not in q:
            prices[sym] = q.get("price", 0)
    triggered = check_alerts(prices)

    # Check RSI thresholds
    for sym in wl["symbols"]:
        alert = wl["alerts"].get(sym, {})
        rsi_thresh = alert.get("rsi_threshold")
        if rsi_thresh is not None:
            from .agent_tools import check_rsi_threshold as check_rsi
            rsi_result = check_rsi(sym, float(rsi_thresh))
            if "error" not in rsi_result and rsi_result.get("is_oversold"):
                triggered.append({
                    "symbol": sym,
                    "reason": f"RSI超跌（RSI={rsi_result['rsi']:.1f}，阈值{rsi_thresh}）",
                    "price": prices.get(sym, 0),
                })

    return {"triggered": triggered}


@app.get("/watchlist/rsi")
async def watchlist_rsi(symbol: str, threshold: float = 30, period: str = "6mo"):
    """Check RSI threshold for a symbol."""
    result = check_rsi_threshold(symbol, threshold, period)
    if "error" in result:
        raise HTTPException(status_code=400, detail=result["error"])
    return result


class TTSRequest(BaseModel):
    text: str


@app.post("/tts")
async def tts_speak(req: TTSRequest):
    """Speak text via Windows TTS."""
    result = speak(req.text)
    if "error" in result:
        raise HTTPException(status_code=500, detail=result["error"])
    return result


@app.post("/watchlist/alert/trigger")
async def watchlist_trigger_alerts():
    """Manually trigger check and push notifications for any triggered alerts."""
    wl = wl_get_all()
    prices = {}
    for sym in wl["symbols"]:
        from .agent_tools import get_quote
        q = get_quote(sym)
        if "error" not in q:
            prices[sym] = q.get("price", 0)
    triggered = check_alerts(prices)

    # Bollinger squeeze check
    for sym in wl["symbols"]:
        sq = calc_bollinger_squeeze(sym)
        if "error" not in sq and sq.get("is_squeeze"):
            triggered.append({
                "symbol": sym,
                "reason": f"布林带收口（带宽{sq['bandwidth']:.2f}，历史分位{sq['percentile_rank']:.0f}%）",
                "price": prices.get(sym, 0),
            })

    # Load TTS preference from config
    enable_tts = False
    config_path = Path.home() / ".stock-analysis-agent" / "config.json"
    if config_path.exists():
        try:
            cfg = json.loads(config_path.read_text())
            enable_tts = cfg.get("enable_tts", False)
        except Exception:
            pass

    for alert in triggered:
        msg = f"🚨 [{alert['symbol']}] {alert['reason']}"
        # TTS speak
        if enable_tts:
            sym = alert["symbol"]
            price = alert.get("price", 0)
            from .agent_tools import get_quote
            q = get_quote(sym)
            chg = q.get("change_pct", 0) if "error" not in q else 0
            speak_price(sym, price, chg, alert.get("reason", ""))
        # ServerChan push
        sckey = None
        if config_path.exists():
            try:
                cfg = json.loads(config_path.read_text())
                sckey = cfg.get("serverchan_sckey") or cfg.get("sckey")
            except Exception:
                pass
        if sckey:
            try:
                import urllib.request
                import urllib.parse
                url = f"https://wxpusher.zjiecode.com/api/send/message/?appToken={sckey}&content={urllib.parse.quote(msg)}&contentType=1"
                req_n = urllib.request.Request(url, headers={"User-Agent": "StockAnalysisAgent/1.0"})
                urllib.request.urlopen(req_n, timeout=5)
            except Exception:
                pass
    return {"triggered": triggered, "notified": len(triggered), "tts": enable_tts}


def _extract_signal(results: list[dict]) -> str | None:
    """Extract bull/bear/neutral signal from tool results."""
    summary = next((r for r in results if r.get("tool") == "get_summary"), None)
    if summary:
        data = summary.get("data", {})
        sig = data.get("signal", "").lower()
        if "bull" in sig or "buy" in sig or "做多" in sig:
            return "bullish"
        if "bear" in sig or "sell" in sig or "做空" in sig:
            return "bearish"
    return "neutral"
