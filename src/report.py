"""Report generator — formats tool results into human-readable analysis reports."""

from __future__ import annotations



def format_report(symbol: str, task: str, results: list[dict]) -> str:
    """Format all tool results into a coherent analysis report."""
    lines = []
    lines.append(f"{'='*60}")
    lines.append(f"  📊 股票分析报告 — {symbol}")
    lines.append(f"{'='*60}")
    lines.append(f"  任务: {task}")
    lines.append(f"  数据来源: {' / '.join(_detect_sources(results))}")
    lines.append(f"{'='*60}\n")

    for r in results:
        name = r.get("tool", "unknown")
        data = r.get("data", {})
        error = r.get("error")

        if error:
            lines.append(f"[{name}] ❌ 错误: {error}\n")
            continue

        if name == "get_quote":
            lines.append(_format_quote(data))
        elif name == "get_a_share_quote":
            lines.append(_format_a_share_quote(data))
        elif name == "get_fundamentals":
            lines.append(_format_fundamentals(data))
        elif name == "calc_all":
            lines.append(_format_all_indicators(data))
        elif name == "calc_rsi":
            lines.append(_format_rsi(data))
        elif name == "calc_macd":
            lines.append(_format_macd(data))
        elif name == "calc_bollinger":
            lines.append(_format_bollinger(data))
        elif name == "calc_kdj":
            lines.append(_format_kdj(data))
        elif name == "calc_atr":
            lines.append(_format_atr(data))
        elif name == "analyze_trend":
            lines.append(_format_trend(data))
        elif name == "get_summary":
            lines.append(_format_summary(data))
        else:
            lines.append(f"[{name}]\n  {data}\n")

    lines.append(_generate_signal(results))
    return "\n".join(lines)


def _detect_sources(results: list[dict]) -> list[str]:
    sources = set()
    for r in results:
        data = r.get("data", {})
        if isinstance(data, dict) and "source" in data:
            sources.add(data["source"])
        elif isinstance(data, dict):
            for v in data.values():
                if isinstance(v, dict) and "source" in v:
                    sources.add(v["source"])
    return list(sources) if sources else ["unknown"]


def _format_quote(data: dict) -> str:
    if "error" in data:
        return f"[get_quote] ❌ {data['error']}\n"
    lines = [
        "",
        "📈 实时报价",
        "-" * 40,
        f"  股票: {data.get('name', data.get('symbol', ''))}",
        f"  价格: ${data.get('price', 'N/A')}",
        f"  开盘: ${data.get('open', 'N/A')}",
        f"  最高: ${data.get('high', 'N/A')}",
        f"  最低: ${data.get('low', 'N/A')}",
        f"  成交量: {_fmt_vol(data.get('volume', 0))}",
        f"  交易所: {data.get('exchange', 'N/A')}",
        f"  时间: {data.get('timestamp', 'N/A')}",
        "",
    ]
    return "\n".join(lines)


def _format_a_share_quote(data: dict) -> str:
    if "error" in data:
        return f"[get_a_share_quote] ❌ {data['error']}\n"
    lines = [
        "",
        "📈 A股实时报价",
        "-" * 40,
        f"  股票: {data.get('name', data.get('symbol', ''))} ({data.get('symbol', '')})",
        f"  价格: ¥{data.get('price', 'N/A')}",
        f"  涨跌: {data.get('change_pct', 'N/A')}% ({data.get('change_abs', 'N/A')})",
        f"  开盘: ¥{data.get('open', 'N/A')}",
        f"  最高: ¥{data.get('high', 'N/A')}",
        f"  最低: ¥{data.get('low', 'N/A')}",
        f"  成交量: {_fmt_vol(data.get('volume', 0))}",
        f"  市盈率 P/E: {data.get('pe', 'N/A')}",
        f"  市净率 P/B: {data.get('pb', 'N/A')}",
        f"  总市值: {_fmt_market_cap(data.get('market_cap', 0))}",
        "",
    ]
    return "\n".join(lines)


def _format_fundamentals(data: dict) -> str:
    if "error" in data:
        return f"[get_fundamentals] ❌ {data['error']}\n"
    lines = [
        "",
        "🏢 基本面数据",
        "-" * 40,
    ]
    for k, v in data.items():
        if k in ("symbol", "name", "source", "timestamp", "error"):
            continue
        label = {
            "pe_ratio": "P/E 市盈率",
            "eps": "EPS 每股收益",
            "market_cap": "总市值",
            "revenue": "营收",
            "net_income": "净利润",
            "roe": "ROE 净资产收益率",
            "debt_to_equity": "资产负债率",
            "dividend_yield": "股息率",
            "beta": "Beta 波动率",
            "52w_high": "52周最高",
            "52w_low": "52周最低",
        }.get(k, k)
        if isinstance(v, (int, float)) and v > 1e8:
            lines.append(f"  {label}: {_fmt_market_cap(v)}")
        else:
            lines.append(f"  {label}: {v}")
    lines.append("")
    return "\n".join(lines)


def _format_all_indicators(data: dict) -> str:
    if "error" in data:
        return f"[calc_all] ❌ {data['error']}\n"
    lines = [
        "",
        "📊 技术指标综合",
        "-" * 40,
    ]
    macd = data.get("macd", {})
    if macd:
        cur = macd.get("current", macd)
        lines.append(f"  MACD: {cur.get('macd', 'N/A'):.4f} | Signal: {cur.get('signal', 'N/A'):.4f} | Hist: {cur.get('histogram', 'N/A'):.4f}")
    rsi = data.get("rsi", {})
    if rsi:
        val = rsi.get("current", rsi.get("value", "N/A"))
        sig = rsi.get("signal", "")
        emoji = "🔴" if sig == "overbought" else "🟢" if sig == "oversold" else "⚪"
        lines.append(f"  RSI(14): {val} {emoji} ({sig})")
    bb = data.get("bollinger", {})
    if bb:
        cur = bb.get("current", bb)
        lines.append(f"  布林带: 上轨 {cur.get('upper', 'N/A')} | 中轨 {cur.get('middle', 'N/A')} | 下轨 {cur.get('lower', 'N/A')}")
        lines.append(f"  布林位置: {cur.get('position_pct', 'N/A')}% ({bb.get('signal', '')})")
    kdj = data.get("kdj", {})
    if kdj:
        cur = kdj.get("current", kdj)
        lines.append(f"  KDJ: K={cur.get('K', 'N/A')} D={cur.get('D', 'N/A')} J={cur.get('J', 'N/A')}")
    atr = data.get("atr", "N/A")
    if atr not in ("N/A", None):
        lines.append(f"  ATR(14): {atr}")
    lines.append("")
    return "\n".join(lines)


def _format_rsi(data: dict) -> str:
    val = data.get("current", "N/A")
    sig = data.get("signal", "")
    emoji = "🔴" if sig == "overbought" else "🟢" if sig == "oversold" else "⚪"
    return f"\n📊 RSI(14): {val} {emoji} ({sig})\n"


def _format_macd(data: dict) -> str:
    cur = data.get("current", {})
    hist = cur.get("histogram", 0)
    hist_str = f"{hist:.4f}"
    hist_emoji = "🟢" if hist > 0 else "🔴" if hist < 0 else "⚪"
    lines = [
        "",
        "📊 MACD",
        "-" * 40,
        f"  MACD Line: {cur.get('macd', 'N/A'):.4f}",
        f"  Signal Line: {cur.get('signal', 'N/A'):.4f}",
        f"  Histogram: {hist_emoji} {hist_str}",
        f"  金叉/死叉次数: {data.get('count', 0)}",
    ]
    crossovers = data.get("crossovers", [])
    if crossovers:
        recent = crossovers[-3:]
        lines.append("  最近交叉:")
        for c in recent:
            emoji = "🟢" if c["type"] == "golden_cross" else "🔴"
            lines.append(f"    {emoji} {c['date']} {c['type']}")
    lines.append("")
    return "\n".join(lines)


def _format_bollinger(data: dict) -> str:
    cur = data.get("current", {})
    sig = data.get("signal", "")
    sig_emoji = "🔴" if sig == "overbought" else "🟢" if sig == "oversold" else "⚪"
    lines = [
        "",
        "📊 布林带 (Bollinger Bands)",
        "-" * 40,
        f"  上轨: {cur.get('upper', 'N/A')}",
        f"  中轨: {cur.get('middle', 'N/A')}",
        f"  下轨: {cur.get('lower', 'N/A')}",
        f"  当前价格: {cur.get('close', 'N/A')}",
        f"  位置: {cur.get('position_pct', 'N/A')}% {sig_emoji}",
    ]
    lines.append("")
    return "\n".join(lines)


def _format_kdj(data: dict) -> str:
    cur = data.get("current", {})
    lines = [
        "",
        "📊 KDJ",
        "-" * 40,
        f"  K: {cur.get('K', 'N/A')} | D: {cur.get('D', 'N/A')} | J: {cur.get('J', 'N/A')}",
    ]
    crossovers = data.get("crossovers", [])
    if crossovers:
        recent = crossovers[-3:]
        for c in recent:
            emoji = "🟢" if c["type"] == "golden_cross" else "🔴"
            lines.append(f"  {emoji} {c['date']} {c['type']}")
    lines.append("")
    return "\n".join(lines)


def _format_atr(data: dict) -> str:
    val = data.get("current", "N/A")
    return f"\n📊 ATR(14): {val} (波动率指标)\n"


def _format_trend(data: dict) -> str:
    if "error" in data:
        return f"[analyze_trend] ❌ {data['error']}\n"
    lines = [
        "",
        "📈 趋势分析 (MA Crossover)",
        "-" * 40,
        f"  趋势: {data.get('trend', 'N/A')}",
        f"  强度: {data.get('strength', 'N/A')}",
        f"  MA5: {data.get('ma5', 'N/A')} | MA20: {data.get('ma20', 'N/A')} | MA60: {data.get('ma60', 'N/A')}",
    ]
    signals = data.get("signals", [])
    if signals:
        lines.append("  信号:")
        for s in signals[-3:]:
            emoji = "🟢" if s.get("type") == "golden_cross" else "🔴"
            lines.append(f"    {emoji} {s.get('date','N/A')} {s.get('type','N/A')} {s.get('ma_type','')}")
    lines.append("")
    return "\n".join(lines)


def _format_summary(data: dict) -> str:
    if "error" in data:
        return f"[get_summary] ❌ {data['error']}\n"
    lines = [
        "",
        "📋 综合摘要",
        "-" * 40,
        f"  股票: {data.get('name', data.get('symbol', ''))}",
        f"  当前价格: {data.get('current_price', 'N/A')}",
        f"  趋势: {data.get('trend', 'N/A')}",
        f"  信号: {data.get('signal', 'N/A')}",
    ]
    indicators = data.get("indicators", {})
    if indicators:
        lines.append(f"  RSI: {indicators.get('rsi', 'N/A')} → {indicators.get('rsi_signal', 'N/A')}")
        lines.append(f"  MACD: {indicators.get('macd', 'N/A')} → {indicators.get('macd_signal', 'N/A')}")
    lines.append("")
    return "\n".join(lines)


def _generate_signal(results: list[dict]) -> str:
    """Generate overall trading signal from all indicators."""
    bullish = 0
    bearish = 0
    neutral = 0

    for r in results:
        data = r.get("data")
        if data is None:
            continue
        # RSI: value may be at data["rsi"]["current"] or data["current"] flat
        if "rsi" in r.get("tool", "") or (isinstance(data, dict) and "rsi" in data):
            rsi_entry = (data.get("rsi", {}) if isinstance(data, dict) else {})
            rsi_val = rsi_entry.get("current") or rsi_entry.get("value")
            if isinstance(rsi_val, dict):
                rsi_val = rsi_val.get("value")
            # Also check flat "current" key (e.g. {"current": 85})
            if not rsi_val and isinstance(data, dict):
                rsi_val = data.get("current") or data.get("value")
            if rsi_val and isinstance(rsi_val, (int, float)):
                if rsi_val > 70:
                    bearish += 1
                elif rsi_val < 30:
                    bullish += 1
                else:
                    neutral += 1
        # MACD histogram: may be at data["macd"]["current"]["histogram"] or flat
        macd_data = (data.get("macd", {}) or {}) if isinstance(data, dict) else {}
        cur = macd_data.get("current", macd_data)
        hist = cur.get("histogram") or cur.get("hist")
        if hist is not None and isinstance(hist, (int, float)):
            if hist > 0:
                bullish += 1
            else:
                bearish += 1
        # KDJ crossovers
        kdj_data = (data.get("kdj", {}) or {}) if isinstance(data, dict) else {}
        crossovers = kdj_data.get("crossovers", []) or []
        if crossovers:
            recent = crossovers[-1] if crossovers else {}
            if recent.get("type") == "golden_cross":
                bullish += 1
            elif recent.get("type") == "death_cross":
                bearish += 1

    total = bullish + bearish + neutral
    if total == 0:
        return ""
    pct_bull = bullish / total * 100
    lines = [
        "",
        f"{'='*60}",
        "🎯 综合信号",
        "-" * 40,
        f"  看涨指标: {bullish} | 看跌指标: {bearish} | 中性: {neutral}",
    ]
    if pct_bull >= 60:
        lines.append(f"  总评: 🟢 偏多 ({pct_bull:.0f}% 看涨信号)")
    elif pct_bull <= 40:
        lines.append(f"  总评: 🔴 偏空 ({pct_bull:.0f}% 看涨信号)")
    else:
        lines.append(f"  总评: ⚪ 中性 ({pct_bull:.0f}% 看涨信号)")
    lines.append(f"{'='*60}\n")
    return "\n".join(lines)


def _fmt_vol(v: int) -> str:
    if v >= 1e9:
        return f"{v/1e9:.2f}B"
    elif v >= 1e6:
        return f"{v/1e6:.2f}M"
    elif v >= 1e3:
        return f"{v/1e3:.1f}K"
    return str(v)


def _fmt_market_cap(v) -> str:
    try:
        v = float(v)
    except (TypeError, ValueError):
        return str(v)
    if v >= 1e12:
        return f"${v/1e12:.2f}T"
    elif v >= 1e9:
        return f"${v/1e9:.2f}B"
    elif v >= 1e6:
        return f"${v/1e6:.2f}M"
    return f"${v:.2f}"


# ── Multi-Agent Debate Report Sections ──────────────────────────────────────

def format_debate_report(symbol: str, query: str, debate_result: dict) -> str:
    """Format full multi-agent debate report.

    Args:
        symbol: Stock ticker
        query: Original user query
        debate_result: Dict from agent.analyze_parallel(use_debate=True)
            {
                "tool_results": [...],
                "bull_case": str,
                "bear_case": str,
                "synthesis": dict
            }
    """
    tool_results = debate_result.get("tool_results", [])
    bull_case = debate_result.get("bull_case", "")
    bear_case = debate_result.get("bear_case", "")
    debate_history = debate_result.get("debate_history", [])
    synthesis = debate_result.get("synthesis", {})

    lines = []
    lines.append(f"{'='*60}")
    lines.append(f"  🤖 多智能体辩论分析报告 — {symbol}")
    lines.append(f"{'='*60}")
    lines.append(f"  任务: {query}")
    lines.append(f"{'='*60}\n")

    # ── Analyst Results ──────────────────────────────────────────────────────
    lines.append(format_report(symbol, query, tool_results))

    # ── Full Debate History ──────────────────────────────────────────────────
    if debate_history:
        lines.append("")
        lines.append(f"{'='*60}")
        lines.append("  🔄 辩论过程")
        lines.append(f"{'='*60}")

        for entry in debate_history:
            speaker = "🟢 多头" if entry["speaker"] == "bull" else "🔴 空头"
            round_num = entry["round"]
            msg_type = {"opening": "开场陈述", "rebuttal": "反驳", "closing": "最终陈述"}.get(entry["type"], entry["type"])
            lines.append(f"\n  ### 第{round_num}轮 - {speaker} ({msg_type})")
            lines.append(f"  {entry['content'][:500]}")

    else:
        # Fallback to simple bull/bear display
        lines.append("")
        lines.append(f"{'='*60}")
        lines.append("  🟢 多头研究员观点")
        lines.append(f"{'='*60}")
        lines.append(bull_case if bull_case else "[无多头观点]")

        lines.append("")
        lines.append(f"{'='*60}")
        lines.append("  🔴 空头研究员观点")
        lines.append(f"{'='*60}")
        lines.append(bear_case if bear_case else "[无空头观点]")

    # ── Synthesis ───────────────────────────────────────────────────────────
    lines.append("")
    lines.append(f"{'='*60}")
    lines.append("  📋 交易决策")
    lines.append(f"{'='*60}")

    decision = synthesis.get("decision", "HOLD")
    confidence = synthesis.get("confidence", 0.0)
    reasoning = synthesis.get("reasoning", "N/A")
    entry = synthesis.get("entry_price", "N/A")
    stop_loss = synthesis.get("stop_loss", "N/A")
    target = synthesis.get("target_price", "N/A")
    risk = synthesis.get("risk_level", "中")
    horizon = synthesis.get("time_horizon", "中期")

    decision_emoji = {"BUY": "🟢", "SELL": "🔴", "HOLD": "⚪"}.get(decision, "⚪")

    lines.append(f"  决策: {decision_emoji} {decision}")
    lines.append(f"  置信度: {confidence:.0%}")
    lines.append(f"  风险等级: {risk}")
    lines.append(f"  时间视野: {horizon}")
    lines.append(f"  入场参考价: {entry}")
    lines.append(f"  止损位: {stop_loss}")
    lines.append(f"  目标价: {target}")
    lines.append("")
    lines.append(f"  决策理由:")
    lines.append(f"  {reasoning}")
    lines.append(f"{'='*60}\n")

    return "\n".join(lines)
