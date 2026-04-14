"""Bull/Bear debate module for multi-agent stock analysis.

Implements the researcher team from TradingAgents:
- bull_researcher: Constructs bullish investment case
- bear_researcher: Constructs bearish investment case
- Both researchers debate analyst findings in structured rounds.
"""

from __future__ import annotations

import os
import textwrap
import time

from .llm import _get_client

DEFAULT_MODEL = os.environ.get("ANTHROPIC_MODEL", "MiniMax-M2.7")
MAX_RETRIES = 2
RETRY_DELAY = 2.0  # seconds


# ── Prompt Templates ─────────────────────────────────────────────────────────

BULL_RESEARCHER_SYSTEM = textwrap.dedent("""\
    你是一位经验丰富的研究员，专门从市场数据和新闻中寻找做多的理由。
    你的职责是构建最有力的看涨论点。

    分析规则：
    1. 数据驱动：用具体数字和指标支撑每个观点
    2. 多角度思考：基本面、技术面、市场情绪都要考虑
    3. 催化剂意识：识别可能的正面催化剂（政策、产品发布、财报等）
    4. 风险收益比：计算合理的买入区间和目标价位
    5. 回答使用中文，语言简洁专业

    你的结论应该包括：
    - 主要做多理由（3-5条，每条有数据支撑）
    - 目标价位和上涨空间
    - 入场时机建议
    - 主要风险（诚实评估，但结论偏多）
""")

BEAR_RESEARCHER_SYSTEM = textwrap.dedent("""\
    你是一位经验丰富的研究员，专门从市场数据和新闻中寻找做空/谨慎的理由。
    你的职责是构建最有力的看跌/风险警示论点。

    分析规则：
    1. 数据驱动：用具体数字和指标支撑每个观点
    2. 多角度思考：基本面、技术面、市场情绪都要考虑
    3. 风险意识：识别可能的负面催化剂（竞争、监管、财务风险等）
    4. 下跌空间：计算合理的做空区间和止损位
    5. 回答使用中文，语言简洁专业

    你的结论应该包括：
    - 主要做空/谨慎理由（3-5条，每条有数据支撑）
    - 风险警示和下跌空间
    - 止损位建议
    - 主要不确定性（可能导致不及预期）
""")


# ── Researcher Functions ──────────────────────────────────────────────────────

def bull_researcher(symbol: str, query: str, analyst_results: list[dict]) -> str:
    """Generate bullish investment case from analyst results.

    Args:
        symbol: Stock ticker
        query: Original user query
        analyst_results: List of tool execution results

    Returns:
        Structured bullish case as string
    """
    prompt = _build_researcher_prompt(symbol, query, analyst_results, stance="bullish")
    return _call_researcher(BULL_RESEARCHER_SYSTEM, prompt)


def bear_researcher(symbol: str, query: str, analyst_results: list[dict]) -> str:
    """Generate bearish investment case from analyst results.

    Args:
        symbol: Stock ticker
        query: Original user query
        analyst_results: List of tool execution results

    Returns:
        Structured bearish case as string
    """
    prompt = _build_researcher_prompt(symbol, query, analyst_results, stance="bearish")
    return _call_researcher(BEAR_RESEARCHER_SYSTEM, prompt)


# ── Helper Functions ──────────────────────────────────────────────────────────

def _build_researcher_prompt(
    symbol: str,
    query: str,
    analyst_results: list[dict],
    stance: str
) -> str:
    """Build researcher prompt from analyst results."""
    parts = []

    parts.append(f"# {stance.upper()} RESEARCHER: {symbol}")
    parts.append(f"\n## 用户问题\n{query}")
    parts.append("\n## 分析师数据\n")

    for r in analyst_results:
        tool = r.get("tool", "unknown")
        data = r.get("data", {})
        error = r.get("error")

        if error:
            parts.append(f"[{tool}] ❌ {error}")
            continue

        if tool == "get_quote":
            parts.append("\n### 报价数据\n")
            parts.append(f"- 价格: ${data.get('price', 'N/A')}")
            parts.append(f"- 涨跌幅: {data.get('change_pct', 'N/A')}%")
            parts.append(f"- 52周范围: ${data.get('year52_low', 'N/A')} - ${data.get('year52_high', 'N/A')}")

        elif tool == "get_a_share_quote":
            parts.append("\n### A股报价\n")
            parts.append(f"- 价格: ¥{data.get('price', 'N/A')}")
            parts.append(f"- 涨跌幅: {data.get('change_pct', 'N/A')}%")
            parts.append(f"- 52周范围: ¥{data.get('year52_low', 'N/A')} - ¥{data.get('year52_high', 'N/A')}")

        elif tool == "get_fundamentals":
            parts.append("\n### 基本面\n")
            parts.append(f"- P/E: {data.get('pe_ratio', 'N/A')}")
            parts.append(f"- EPS: {data.get('eps', 'N/A')}")
            parts.append(f"- ROE: {data.get('roe', 'N/A')}")
            parts.append(f"- 分析师建议: {data.get('recommendation', 'N/A')}")

        elif tool == "calc_all":
            macd = data.get("macd", {})
            rsi = data.get("rsi", {})
            bb = data.get("bollinger", {})
            atr = data.get("atr", "N/A")

            parts.append("\n### 技术指标\n")
            parts.append(f"- MACD: {macd.get('histogram', 0):.4f} (正=看涨)")
            parts.append(f"- RSI: {rsi.get('value', 'N/A')} ({rsi.get('signal', '')})")
            parts.append(f"- 布林带位置: {bb.get('position_pct', 'N/A')}%")
            parts.append(f"- ATR: {atr}")

        elif tool == "calc_rsi":
            parts.append("\n### RSI\n")
            parts.append(f"- 值: {data.get('current', 'N/A')}")
            parts.append(f"- 信号: {data.get('signal', 'N/A')}")

        elif tool == "calc_macd":
            cur = data.get("current", {})
            parts.append("\n### MACD\n")
            parts.append(f"- MACD: {cur.get('macd', 'N/A')}")
            parts.append(f"- Signal: {cur.get('signal', 'N/A')}")
            parts.append(f"- Histogram: {cur.get('histogram', 'N/A')} (正=看涨)")

        elif tool == "analyze_trend":
            parts.append("\n### 趋势分析\n")
            parts.append(f"- 趋势: {data.get('trend', 'N/A')}")
            parts.append(f"- 强度: {data.get('strength', 'N/A')}")

        elif tool == "get_summary":
            parts.append("\n### 综合摘要\n")
            parts.append(f"- 信号: {data.get('signal', 'N/A')}")
            parts.append(f"- 趋势: {data.get('trend', 'N/A')}")

    parts.append("\n## 你的任务\n")
    if stance == "bullish":
        parts.append("根据以上数据，构建最有力的做多理由。使用中文回答。")
    else:
        parts.append("根据以上数据，构建最有力的做空/谨慎理由。使用中文回答。")

    return "\n".join(parts)


def _call_researcher(system: str, prompt: str, max_tokens: int = 1024) -> str:
    """Call researcher LLM with given system prompt and retry logic."""
    last_error = None
    for attempt in range(MAX_RETRIES + 1):
        try:
            client = _get_client()
            response = client.messages.create(
                model=DEFAULT_MODEL,
                max_tokens=max_tokens,
                system=system,
                messages=[{"role": "user", "content": prompt}],
            )

            for block in response.content:
                if hasattr(block, "type") and block.type == "text":
                    return block.text

            return str(response.content)
        except Exception as e:
            last_error = e
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY)
                continue
    return f"[研究员分析失败: {last_error}]"


# ── Multi-Round Debate ────────────────────────────────────────────────────────

def run_debate(
    symbol: str,
    query: str,
    analyst_results: list[dict],
    max_rounds: int = 2,
) -> dict:
    """Run multi-round bull/bear debate.

    Args:
        symbol: Stock ticker
        query: Original user query
        analyst_results: Analyst tool results
        max_rounds: Number of rebuttal rounds (default 2)

    Returns:
        {
            "bull_case": str,
            "bear_case": str,
            "debate_history": [...],
            "final_bull": str,
            "final_bear": str,
        }
    """
    if max_rounds < 1:
        max_rounds = 1

    # Round 0: Initial arguments
    bull_case = bull_researcher(symbol, query, analyst_results)
    bear_case = bear_researcher(symbol, query, analyst_results)

    debate_history = [
        {"round": 0, "speaker": "bull", "type": "opening", "content": bull_case},
        {"round": 0, "speaker": "bear", "type": "opening", "content": bear_case},
    ]

    # Subsequent rounds: rebuttals
    for round_num in range(1, max_rounds + 1):
        # Bull rebuts bear
        bull_rebuttal_text = _bull_rebuttal(
            symbol, query, analyst_results, bull_case, bear_case, round_num
        )
        debate_history.append({
            "round": round_num,
            "speaker": "bull",
            "type": "rebuttal",
            "content": bull_rebuttal_text,
        })
        bull_case = bull_rebuttal_text  # Update with latest

        # Bear rebuts bull
        bear_rebuttal_text = _bear_rebuttal(
            symbol, query, analyst_results, bull_case, bear_case, round_num
        )
        debate_history.append({
            "round": round_num,
            "speaker": "bear",
            "type": "rebuttal",
            "content": bear_rebuttal_text,
        })
        bear_case = bear_rebuttal_text  # Update with latest

    # Final closing statements
    final_bull = _bull_closing(symbol, query, analyst_results, bull_case, bear_case)
    final_bear = _bear_closing(symbol, query, analyst_results, bull_case, bear_case)

    debate_history.append({
        "round": max_rounds + 1,
        "speaker": "bull",
        "type": "closing",
        "content": final_bull,
    })
    debate_history.append({
        "round": max_rounds + 1,
        "speaker": "bear",
        "type": "closing",
        "content": final_bear,
    })

    return {
        "bull_case": bull_case,
        "bear_case": bear_case,
        "debate_history": debate_history,
        "final_bull": final_bull,
        "final_bear": final_bear,
    }


# ── Rebuttal Prompts ───────────────────────────────────────────────────────────

def _bull_rebuttal(
    symbol: str,
    query: str,
    analyst_results: list[dict],
    current_bull: str,
    current_bear: str,
    round_num: int,
) -> str:
    """Bull researcher rebuts bear's arguments."""
    prompt = f"""# 多空辩论 — 第 {round_num} 轮: 多头反驳

## 股票: {symbol}
## 用户问题: {query}

## 你（多头）之前的观点:
{current_bull}

## 空头的观点:
{current_bear}

## 你的任务:
针对空头的观点进行反驳。指出空头论点的弱点，用数据支持你的反驳。
使用中文回答，简洁有力。"""

    return _call_researcher(BULL_RESEARCHER_SYSTEM + "\n\n[追加规则: 这是第" + str(round_num) + "轮反驳，你必须针对对方的具体论点进行反驳]", prompt)


def _bear_rebuttal(
    symbol: str,
    query: str,
    analyst_results: list[dict],
    current_bull: str,
    current_bear: str,
    round_num: int,
) -> str:
    """Bear researcher rebuts bull's arguments."""
    prompt = f"""# 多空辩论 — 第 {round_num} 轮: 空头反驳

## 股票: {symbol}
## 用户问题: {query}

## 多头的观点:
{current_bull}

## 你（空头）之前的观点:
{current_bear}

## 你的任务:
针对多头的观点进行反驳。指出多头论点的弱点，用数据支持你的反驳。
使用中文回答，简洁有力。"""

    return _call_researcher(BEAR_RESEARCHER_SYSTEM + "\n\n[追加规则: 这是第" + str(round_num) + "轮反驳，你必须针对对方的具体论点进行反驳]", prompt)


def _bull_closing(
    symbol: str,
    query: str,
    analyst_results: list[dict],
    current_bull: str,
    current_bear: str,
) -> str:
    """Bull researcher's closing statement."""
    prompt = f"""# 多头最终陈述

## 股票: {symbol}

## 空头的质疑:
{current_bear}

## 你（多头）经过辩论后的最终立场:
{current_bull}

## 你的任务:
作为多头研究员，给出最终陈述。承认空头的合理质疑，但重申你的核心做多理由。
给出最终投资建议（买入价、目标价、止损位）。
使用中文回答。"""

    return _call_researcher(BULL_RESEARCHER_SYSTEM, prompt, max_tokens=512)


def _bear_closing(
    symbol: str,
    query: str,
    analyst_results: list[dict],
    current_bull: str,
    current_bear: str,
) -> str:
    """Bear researcher's closing statement."""
    prompt = f"""# 空头最终陈述

## 股票: {symbol}

## 多头的论点:
{current_bull}

## 你（空头）经过辩论后的最终立场:
{current_bear}

## 你的任务:
作为空头研究员，给出最终陈述。承认多头的合理观点，但强调你的核心风险警示。
给出最终投资建议（是否应该回避、止损位建议）。
使用中文回答。"""

    return _call_researcher(BEAR_RESEARCHER_SYSTEM, prompt, max_tokens=512)
