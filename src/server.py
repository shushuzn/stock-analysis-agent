"""MCP server wrapper for Stock Analysis Agent.

Exposes the ReAct agent as an MCP tool so it can be used by Claude Code / OpenClaw.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# Ensure sibling stock-analysis-mcp is importable
_mcp_path = Path(__file__).parent.parent.parent / "stock-analysis-mcp" / "src"
if str(_mcp_path) not in sys.path:
    sys.path.insert(0, str(_mcp_path))

from .agent import ReActAgent, extract_symbol
from .report import format_report


# ── MCP Protocol Handlers ─────────────────────────────────────────────────────

def handle_initialize(params: dict) -> dict:
    return {
        "protocolVersion": "2024-11-05",
        "capabilities": {"tools": {}},
        "serverInfo": {"name": "stock-analysis-agent", "version": "0.1.0"},
    }


def handle_tools_list() -> dict:
    return {
        "tools": [
            {
                "name": "stock_analysis",
                "description": "Analyze a stock using natural language query. Returns comprehensive report with quote, technical indicators, fundamentals, and trading signal. Supports US stocks (AAPL, NVDA) and China A-shares (600519, 000001).",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string",
                            "description": "Natural language analysis request, e.g. '分析苹果最近趋势' or 'AAPL RSI MACD分析' or '贵州茅台技术面'",
                        },
                        "symbol": {
                            "type": "string",
                            "description": "Stock ticker or A-share code. Auto-detected if not provided. Examples: AAPL, NVDA, 600519, 000001",
                        },
                        "period": {
                            "type": "string",
                            "description": "Historical period for technical indicators: 1mo, 3mo, 6mo, 1y, 2y. Default: 6mo",
                            "default": "6mo",
                        },
                    },
                    "required": ["query"],
                },
            },
            {
                "name": "list_stock_tools",
                "description": "List all available stock analysis tools with descriptions.",
                "inputSchema": {"type": "object", "properties": {}},
            },
        ]
    }


def handle_tools_call(name: str, arguments: dict) -> dict:
    if name == "list_stock_tools":
        from tools import list_tools
        tools = list_tools()
        return {
            "content": [{"type": "text", "text": json.dumps({"tools": tools}, ensure_ascii=False)}]
        }

    if name == "stock_analysis":
        query = arguments.get("query", "")
        symbol = arguments.get("symbol", "") or extract_symbol(query)
        period = arguments.get("period", "6mo")

        if not symbol:
            return {
                "content": [{"type": "text", "text": json.dumps({"error": "Could not detect stock symbol. Please provide it explicitly.", "example": "query: '分析趋势', symbol: 'AAPL'"}, ensure_ascii=False)}]
            }

        agent = ReActAgent(max_steps=10, verbose=False)
        try:
            results = agent.analyze(query, symbol)
        except Exception as e:
            return {
                "content": [{"type": "text", "text": json.dumps({"error": str(e)}, ensure_ascii=False)}]
            }

        report = format_report(symbol, query, results)
        return {
            "content": [{"type": "text", "text": report}]
        }

    return {
        "content": [{"type": "text", "text": json.dumps({"error": f"Unknown tool: {name}"}, ensure_ascii=False)}]
    }


def handle_request(message: dict) -> dict:
    method = message.get("method", "")
    msg_id = message.get("id")
    params = message.get("params", {})

    if method == "initialize":
        return {"id": msg_id, "result": handle_initialize(params)}
    elif method == "tools/list":
        return {"id": msg_id, "result": handle_tools_list()}
    elif method == "tools/call":
        tool_name = params.get("name", "")
        tool_args = params.get("arguments", {})
        return {"id": msg_id, "result": handle_tools_call(tool_name, tool_args)}
    elif method == "notifications/initialized":
        return None  # Notification, no response
    else:
        return {"id": msg_id, "error": {"code": -32601, "message": f"Unknown method: {method}"}}


def main():
    """Read JSON-RPC requests from stdin, write responses to stdout."""
    while True:
        line = sys.stdin.readline()
        if not line:
            break
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue

        response = handle_request(message)
        if response is not None:
            print(json.dumps(response), flush=True)


if __name__ == "__main__":
    main()
