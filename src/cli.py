"""CLI interface for stock analysis agent."""

from __future__ import annotations

import argparse
import json
import time

from .agent import ReActAgent, extract_symbol
from .agent_tools import list_tools
from .report import format_debate_report, format_report


def run_analysis(symbol: str, query: str, args) -> dict | list | str:
    """Run the analysis and return raw results or formatted report."""
    agent = ReActAgent(max_steps=10, verbose=args.verbose)

    if args.debate:
        # Multi-agent debate mode
        result = agent.analyze_with_debate(query, symbol)
        if args.format == "json":
            return result
        return format_debate_report(symbol, query, result)

    # Normal parallel analysis
    results = agent.analyze_parallel(query, symbol)
    return results


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
    parser.add_argument(
        "--format", "-f",
        default="text",
        choices=["text", "json"],
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--watch", "-w",
        metavar="SECONDS",
        type=int,
        help="Watch mode: refresh analysis every N seconds",
    )
    parser.add_argument(
        "--debate",
        action="store_true",
        help="Enable multi-agent bull/bear debate",
    )
    parser.add_argument(
        "--max-rounds",
        type=int,
        default=2,
        help="Number of debate rebuttal rounds (default: 2)",
    )

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
        print("  stock-agent --debate '特斯拉值得投资吗'")
        print("  stock-agent --watch 60 'AAPL技术分析'")
        print("  stock-agent -f json 'AAPL' -s AAPL")
        print("  stock-agent --list-tools")
        return

    # Extract symbol
    symbol = args.symbol or extract_symbol(args.query)
    if not symbol:
        print("❌ Could not detect stock symbol. Please specify with -s/--symbol")
        print("   Example: stock-agent '分析趋势' -s AAPL")
        return

    # Configure agent for debate rounds
    if args.debate:
        import functools

        from .debate import run_debate
        _orig_run_debate = run_debate
        run_debate = functools.partial(_orig_run_debate, max_rounds=args.max_rounds)

    def do_analysis():
        print(f"\n🔍 Analyzing {symbol} ...\n")
        try:
            result = run_analysis(symbol, args.query, args)
        except Exception as e:
            print(f"❌ Agent error: {e}")
            if args.verbose:
                import traceback
                traceback.print_exc()
            return False

        if not result:
            print("❌ No results produced")
            return False

        if args.format == "json":
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            if isinstance(result, list):
                print(format_report(symbol, args.query, result))
            else:
                print(result)
        return True

    # Run once or watch mode
    if args.watch:
        print(f"👀 Watch mode: refreshing every {args.watch}s (Ctrl+C to stop)\n")
        try:
            while True:
                success = do_analysis()
                if not success:
                    print("⚠️  Analysis failed, retrying...\n")
                print(f"\n⏰ Next refresh in {args.watch}s ...\n")
                time.sleep(args.watch)
        except KeyboardInterrupt:
            print("\n\n👋 Watch mode stopped.")
    else:
        do_analysis()


if __name__ == "__main__":
    main()
