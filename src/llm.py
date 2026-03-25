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
            api_key=os.environ.get(
                "ANTHROPIC_API_KEY",
                "sk-cp-zNNt30MolJOgSwdsdgA8BJbLoKmiV3Zttz_IgZkapeyjoPPq-qYFSw-XiMZIIUyeH4PTB4Y86QXu_wKR8JvmZ9PbkkMmMwDTC6QgHznXopDTl0nBZ9AQHQ8",
            ),
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
