"""ReAct Agent for stock analysis.

Implements a Reasoning + Action loop:
  1. Think about what to do
  2. Select and execute a tool
  3. Observe the result
  4. Repeat until done

Inspired by Dify's Agent inference engine but simplified.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

# Use relative import when run as package (python -m), absolute when run as script
if __spec__ is not None and __spec__.parent:
    from .agent_tools import execute_tool, select_tools_for_task
else:
    from agent_tools import execute_tool, select_tools_for_task


@dataclass
class ToolResult:
    tool: str
    args: dict
    data: Any = None
    error: str = ""
    observation: str = ""

    @property
    def success(self) -> bool:
        return self.error == "" and self.data is not None


@dataclass
class ReActAgent:
    """ReAct-based stock analysis agent."""

    max_steps: int = 10
    verbose: bool = False

    _history: list[dict] = field(default_factory=list)
    _steps: int = 0

    def analyze(self, query: str, symbol: str, use_llm: bool = False) -> list[dict] | str:
        """Main entry point: analyze a stock based on natural language query.

        Args:
            query: Natural language task, e.g. "分析苹果最近趋势"
            symbol: Stock ticker or A-share code

        Returns:
            List of ToolResult dicts with all tool execution results
        """
        self._history = []
        self._steps = 0

        # Step 0: Select tools based on task
        selected = select_tools_for_task(query, symbol)
        if self.verbose:
            print(f"[Agent] Selected tools: {[t[0] for t in selected]}")

        # Execute all selected tools sequentially
        results = []
        for tool_name, kwargs in selected:
            self._steps += 1
            if self._steps > self.max_steps:
                if self.verbose:
                    print(f"[Agent] Max steps ({self.max_steps}) reached, stopping")
                break

            if self.verbose:
                print(f"[Agent] Step {self._steps}: Calling {tool_name}({kwargs})")

            try:
                data = execute_tool(tool_name, **kwargs)
                error = data.pop("error", "") if isinstance(data, dict) else ""
                if error and "No data" in error:
                    error = ""  # Not a real error, just no data
                result = ToolResult(tool=tool_name, args=kwargs, data=data, error=error)
            except Exception as e:
                result = ToolResult(tool=tool_name, args=kwargs, error=str(e))

            # Generate observation
            result.observation = self._observe(result)
            self._history.append(self._to_dict(result))
            results.append(self._to_dict(result))

            if self.verbose:
                print(f"  → observation: {result.observation[:80]}")

        # LLM-powered analysis
        if use_llm:
            from .llm import analyze_with_llm
            llm_result = analyze_with_llm(symbol, query, results)
            return llm_result

        return results

    def _observe(self, result: ToolResult) -> str:
        """Generate a natural language observation from tool result."""
        if result.error:
            return f"Error: {result.error}"

        data = result.data
        if not isinstance(data, dict):
            return str(data)[:100]

        tool = result.tool

        if tool == "get_quote":
            price = data.get("price", "?")
            name = data.get("name", "?")
            change = data.get("change_pct", "?")
            return f"{name}当前价格${price}，涨跌{change}%"
        elif tool == "get_a_share_quote":
            price = data.get("price", "?")
            name = data.get("name", "?")
            change = data.get("change_pct", "?")
            return f"{name}({data.get('symbol', '')})当前价格¥{price}，涨跌{change}%"
        elif tool == "calc_rsi":
            val = data.get("current", "?")
            sig = data.get("signal", "?")
            return f"RSI={val}，信号={sig}"
        elif tool == "calc_macd":
            cur = data.get("current", {})
            macd = cur.get("macd", "?")
            hist = cur.get("histogram", "?")
            return f"MACD={macd}，Histogram={hist}"
        elif tool == "calc_bollinger":
            cur = data.get("current", {})
            close = cur.get("close", "?")
            pos = cur.get("position_pct", "?")
            return f"价格{close}，布林位置{pos}%"
        elif tool == "calc_kdj":
            cur = data.get("current", {})
            k = cur.get("K", "?")
            d = cur.get("D", "?")
            j = cur.get("J", "?")
            return f"K={k} D={d} J={j}"
        elif tool == "calc_atr":
            val = data.get("current", "?")
            return f"ATR={val}"
        elif tool == "calc_all":
            rsi = data.get("rsi", {}).get("value", "?")
            macd = data.get("macd", {}).get("histogram", "?")
            return f"RSI={rsi}，MACD Histogram={macd}"
        elif tool == "get_fundamentals":
            pe = data.get("pe_ratio", "?") or data.get("pe", "?")
            mc = data.get("market_cap", "?")
            return f"P/E={pe}，市值={mc}"
        elif tool == "analyze_trend":
            trend = data.get("trend", "?")
            strength = data.get("strength", "?")
            return f"趋势={trend}，强度={strength}"
        elif tool == "get_summary":
            price = data.get("current_price", "?")
            signal = data.get("signal", "?")
            return f"价格={price}，信号={signal}"
        else:
            keys = list(data.keys())[:3]
            return f"返回字段: {keys}"

    def _to_dict(self, result: ToolResult) -> dict:
        return {
            "tool": result.tool,
            "args": result.args,
            "data": result.data,
            "error": result.error,
            "observation": result.observation,
        }

    @property
    def history(self) -> list[dict]:
        return self._history


def extract_symbol(text: str) -> str:
    """Extract stock symbol from natural language query.

    Handles:
    - Direct tickers: AAPL, NVDA, TSLA
    - Chinese stock codes: 600519, 000001
    - Names: "苹果" -> AAPL, "茅台" -> 600519
    """
    text = text.strip()

    # Direct ticker patterns
    us_pattern = r'\b([A-Z]{2,5})\b'
    if m := re.search(us_pattern, text):
        return m.group(1)

    # A-share 6-digit codes
    cn_pattern = r'\b([0-9]{6})\b'
    if m := re.search(cn_pattern, text):
        return m.group(1)

    # Chinese name mapping
    name_map = {
        "苹果": "AAPL",
        "苹果公司": "AAPL",
        "微软": "MSFT",
        "谷歌": "GOOGL",
        "亚马逊": "AMZN",
        "英伟达": "NVDA",
        "特斯拉": "TSLA",
        "Meta": "META",
        "茅台": "600519",
        "贵州茅台": "600519",
        "腾讯": "00700",
        "阿里巴巴": "BABA",
        "京东": "JD",
        "平安": "601318",
        "工行": "601398",
    }
    for name, sym in name_map.items():
        if name in text:
            return sym

    return ""
