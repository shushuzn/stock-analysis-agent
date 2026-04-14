"""LLM-powered analysis module.

Uses MiniMax Anthropic-compatible API to generate natural language
investment analysis with reasoning from technical indicators.
"""

from __future__ import annotations

import os
import textwrap

import anthropic

# ── Client ─────────────────────────────────────────────────────────────────────

_client: anthropic.Anthropic | None = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(
            api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
            base_url=os.environ.get(
                "ANTHROPIC_BASE_URL",
                "https://api.minimaxi.com/anthropic",
            ),
        )
    return _client


# ── Prompt Builder ───────────────────────────────────────────────────────────

def _build_analysis_prompt(symbol: str, query: str, results: list[dict]) -> str:
    """Build the prompt for LLM analysis."""
    # Extract key data
    quote_data = None
    fundamentals = None
    indicators = None
    trend = None

    for r in results:
        data = r.get("data", {})
        if not isinstance(data, dict) or "error" in data:
            continue
        tool = r.get("tool", "")
        if tool in ("get_quote", "get_a_share_quote"):
            quote_data = data
        elif tool == "get_fundamentals":
            fundamentals = data
        elif tool == "calc_all":
            indicators = data
        elif tool == "analyze_trend":
            trend = data

    # Format the data as text
    parts = []

    parts.append(f"你是专业的股票投资分析师。请根据以下数据对 {symbol} 进行分析。")

    if quote_data:
        price = quote_data.get("price", "N/A")
        name = quote_data.get("name", symbol)
        change_pct = quote_data.get("change_pct") or quote_data.get("change", "N/A")
        high = quote_data.get("high", "N/A")
        low = quote_data.get("low", "N/A")
        volume = quote_data.get("volume", "N/A")
        source = quote_data.get("source", "unknown")
        parts.append(f"\n## 最新报价 ({source})\n- 股票: {name} ({symbol})\n- 当前价格: {price}\n- 涨跌幅: {change_pct}%\n- 最高/最低: {high} / {low}\n- 成交量: {volume}")

    if fundamentals:
        pe = fundamentals.get("pe_ratio") or fundamentals.get("pe", "N/A")
        eps = fundamentals.get("eps", "N/A")
        market_cap = fundamentals.get("market_cap", "N/A")
        roe = fundamentals.get("roe", "N/A")
        if isinstance(roe, float):
            roe = f"{roe * 100:.1f}%"
        debt = fundamentals.get("debt_to_equity", "N/A")
        div_yield = fundamentals.get("dividend_yield", "N/A")
        if isinstance(div_yield, float):
            div_yield = f"{div_yield * 100:.2f}%"
        rec = fundamentals.get("recommendation", "N/A")
        parts.append(f"\n## 基本面\n- P/E 市盈率: {pe}\n- EPS 每股收益: {eps}\n- 总市值: {market_cap}\n- ROE 净资产收益率: {roe}\n- 资产负债率: {debt}\n- 股息率: {div_yield}\n- 分析师建议: {rec}")

    if indicators:
        macd = indicators.get("macd", {})
        rsi = indicators.get("rsi", {})
        bb = indicators.get("bollinger", {})
        kdj = indicators.get("kdj", {})
        atr = indicators.get("atr", "N/A")

        macd_val = macd.get("macd", "N/A")
        macd_sig = macd.get("signal", "N/A")
        macd_hist = macd.get("histogram", "N/A")
        rsi_val = rsi.get("value", "N/A")
        rsi_sig = rsi.get("signal", "N/A")
        bb_upper = bb.get("upper", "N/A")
        bb_mid = bb.get("middle", "N/A")
        bb_lower = bb.get("lower", "N/A")
        bb_pos = bb.get("position_pct", "N/A")
        k_val = kdj.get("K", "N/A")
        d_val = kdj.get("D", "N/A")
        j_val = kdj.get("J", "N/A")

        parts.append(f"\n## 技术指标\n- MACD: {macd_val:.4f} | Signal: {macd_sig:.4f} | Histogram: {macd_hist:.4f}\n- RSI(14): {rsi_val} → {rsi_sig}\n- 布林带: 上轨 {bb_upper} | 中轨 {bb_mid} | 下轨 {bb_lower} | 位置 {bb_pos}%\n- KDJ: K={k_val} D={d_val} J={j_val}\n- ATR(14): {atr}")

    if trend:
        t = trend.get("trend", "N/A")
        s = trend.get("strength", "N/A")
        ma5 = trend.get("ma5", "N/A")
        ma20 = trend.get("ma20", "N/A")
        ma60 = trend.get("ma60", "N/A")
        parts.append(f"\n## 趋势分析\n- 趋势: {t}\n- 强度: {s}\n- MA5={ma5} | MA20={ma20} | MA60={ma60}")

    parts.append(f"\n## 用户问题\n{query}")

    return "\n".join(parts)


# ── Analysis ──────────────────────────────────────────────────────────────────

def analyze_with_llm(symbol: str, query: str, results: list[dict]) -> str:
    """Generate LLM-powered analysis from tool results."""
    prompt = _build_analysis_prompt(symbol, query, results)

    system = textwrap.dedent("""\
        你是一位资深股票投资分析师，有十年以上的A股和美股分析经验。
        你的分析必须：
        1. 解释技术指标背后的投资逻辑（RSI>70为什么是超买、MACD金叉为什么看涨）
        2. 结合基本面和技术面给出综合判断
        3. 用中文回答，语言简洁专业
        4. 给出明确的买卖信号和风险提示
        5. 提及具体的价格点位和指标数值作为依据
        不要泛泛而谈，每个结论都要有数据支撑。
    """)

    try:
        client = _get_client()
        response = client.messages.create(
            model=os.environ.get("ANTHROPIC_MODEL", "MiniMax-M2.7"),
            max_tokens=1024,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )

        # Extract text from response
        for block in response.content:
            if hasattr(block, "type") and block.type == "text":
                return block.text

        return str(response.content)
    except Exception as e:
        return f"[LLM分析失败: {e}]"


def bull_bear_synthesis(
    symbol: str,
    query: str,
    analyst_results: list[dict],
    bull_case: str,
    bear_case: str,
    debate_history: list[dict] | None = None,
) -> dict:
    """Synthesize bull/bear debate into final trading decision.

    Implements the Trader agent from TradingAgents:
    - Reviews analyst results, bull case, and bear case
    - Produces structured decision with BUY/SELL/HOLD
    - Includes confidence score and reasoning
    """
    prompt = _build_synthesis_prompt(symbol, query, analyst_results, bull_case, bear_case, debate_history)

    system = textwrap.dedent("""\
        你是一位资深交易员，负责综合多方和空方研究员的分析，
        做出最终的投资决策。

        你的职责：
        1. 客观评估多做理由和做空理由
        2. 判断多空力量对比
        3. 给出明确的交易信号：BUY / SELL / HOLD
        4. 评估置信度和风险
        5. 使用中文回答

        输出格式（严格遵循）：
        {
            "decision": "BUY" | "SELL" | "HOLD",
            "confidence": 0.0-1.0,
            "reasoning": "决策理由...",
            "entry_price": "参考入场价",
            "stop_loss": "止损位",
            "target_price": "目标价",
            "risk_level": "低" | "中" | "高",
            "time_horizon": "短期" | "中期" | "长期"
        }
    """)

    try:
        client = _get_client()
        response = client.messages.create(
            model=os.environ.get("ANTHROPIC_MODEL", "MiniMax-M2.7"),
            max_tokens=512,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )

        text = ""
        for block in response.content:
            if hasattr(block, "type") and block.type == "text":
                text = block.text
                break

        # Parse JSON from response
        import json
        import re
        json_match = re.search(r'\{[^{}]*\}', text, re.DOTALL)
        if json_match:
            return json.loads(json_match.group())
        return {
            "decision": "HOLD",
            "confidence": 0.5,
            "reasoning": text[:200],
            "entry_price": "N/A",
            "stop_loss": "N/A",
            "target_price": "N/A",
            "risk_level": "中",
            "time_horizon": "中期",
        }
    except Exception as e:
        return {
            "decision": "HOLD",
            "confidence": 0.0,
            "reasoning": f"LLM合成失败: {e}",
            "entry_price": "N/A",
            "stop_loss": "N/A",
            "target_price": "N/A",
            "risk_level": "高",
            "time_horizon": "N/A",
        }


def _build_synthesis_prompt(
    symbol: str,
    query: str,
    analyst_results: list[dict],
    bull_case: str,
    bear_case: str,
    debate_history: list[dict] | None = None,
) -> str:
    """Build synthesis prompt from all inputs including debate history."""
    # Format analyst results
    analyst_text = []
    for r in analyst_results:
        tool = r.get("tool", "unknown")
        obs = r.get("observation", "")
        analyst_text.append(f"[{tool}] {obs}")

    parts = [
        f"# 交易决策合成: {symbol}",
        f"\n## 用户问题\n{query}",
        "\n## 分析师数据汇总\n" + "\n".join(analyst_text),
    ]

    # Add debate history if available
    if debate_history:
        parts.append("\n## 辩论过程")
        for entry in debate_history:
            speaker = "🟢 多头" if entry["speaker"] == "bull" else "🔴 空头"
            round_num = entry["round"]
            msg_type = {"opening": "开场", "rebuttal": "反驳", "closing": "结案"}.get(entry["type"], entry["type"])
            content = entry["content"][:300] + "..." if len(entry["content"]) > 300 else entry["content"]
            parts.append(f"\n### 第{round_num}轮 - {speaker} ({msg_type}):\n{content}")
    else:
        parts.append(f"\n## 多头研究员观点\n{bull_case}")
        parts.append(f"\n## 空头研究员观点\n{bear_case}")

    parts.append("\n请根据以上所有信息，做出最终交易决策。")
    return "\n".join(parts)


def analyze_with_llm_streaming(symbol: str, query: str, results: list[dict]):
    """Streaming version of LLM analysis."""
    prompt = _build_analysis_prompt(symbol, query, results)

    system = textwrap.dedent("""\
        你是一位资深股票投资分析师，有十年以上的A股和美股分析经验。
        你的分析必须：
        1. 解释技术指标背后的投资逻辑
        2. 结合基本面和技术面给出综合判断
        3. 用中文回答，语言简洁专业
        4. 给出明确的买卖信号和风险提示
        5. 提及具体的价格点位和指标数值作为依据
    """)

    try:
        client = _get_client()
        with client.messages.stream(
            model=os.environ.get("ANTHROPIC_MODEL", "MiniMax-M2.7"),
            max_tokens=1024,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            for text in stream.text_stream:
                yield text
    except Exception as e:
        yield f"[LLM分析失败: {e}]"
