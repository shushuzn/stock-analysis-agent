"""CLI interface for stock analysis agent."""

from __future__ import annotations

import argparse

from .agent import ReActAgent, extract_symbol
from .report import format_report
from .tools import list_tools


def main():
    parser = argparse.ArgumentParser(
        description="📊 Stock Analysis Agent — AI-powered investment analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "query",
        nargs="?",
        help="Natural language query, e.g. '分析苹果最近趋势' or 'AAPL technical analysis'",
    )
    parser.add_argument("-s", "--symbol", help="Stock symbol (auto-detected if not provided)")
    parser.add_argument("-v", "--verbose", action="store_true", help="Show agent reasoning steps")
    parser.add_argument("--list-tools", action="store_true", help="List all available tools")
    parser.add_argument(
        "--period",
        default="6mo",
        choices=["1mo", "3mo", "6mo", "1y", "2y"],
        help="Historical period for indicators (default: 6mo)",
    )
    parser.add_argument("--agent", action="store_true", help="Use ReAct agent (default: true)")

    args = parser.parse_args()

    if args.list_tools:
        tools = list_tools()
        print(f"\n📦 Available tools ({len(tools)}):\n")
        for t in tools:
            print(f"  {t['name']:20s} — {t['desc']}")
        print()
        return

    if not args.query:
        parser.print_help()
        print("\n💡 Example queries:")
        print("  stock-agent '分析苹果最近趋势'")
        print("  stock-agent 'AAPL RSI MACD分析'")
        print("  stock-agent '贵州茅台基本面' -s 600519")
        print("  stock-agent 'NVDA技术指标'")
        print("  stock-agent --list-tools")
        return

    # Extract symbol
    symbol = args.symbol or extract_symbol(args.query)
    if not symbol:
        print("❌ Could not detect stock symbol. Please specify with -s/--symbol")
        print("   Example: stock-agent '分析趋势' -s AAPL")
        return

    print(f"\n🔍 Analyzing {symbol} ...\n")

    # Run agent
    agent = ReActAgent(max_steps=10, verbose=args.verbose)
    try:
        results = agent.analyze(args.query, symbol)
    except Exception as e:
        print(f"❌ Agent error: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()
        return

    if not results:
        print("❌ No results produced")
        return

    # Format and print report
    report = format_report(symbol, args.query, results)
    print(report)


if __name__ == "__main__":
    main()
