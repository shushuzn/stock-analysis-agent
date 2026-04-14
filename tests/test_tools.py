"""Tests for the tools module."""

from src.agent_tools import execute_tool, list_tools, select_tools_for_task


class TestListTools:
    def test_returns_list(self):
        tools = list_tools()
        assert isinstance(tools, list)

    def test_each_tool_has_required_fields(self):
        tools = list_tools()
        assert len(tools) > 0
        for t in tools:
            assert "name" in t
            assert "desc" in t
            assert "args" in t

    def test_all_expected_tools_present(self):
        tools = list_tools()
        names = [t["name"] for t in tools]
        expected = [
            "get_quote", "get_a_share_quote", "calc_rsi", "calc_macd",
            "calc_bollinger", "calc_kdj", "calc_atr", "calc_all",
            "get_fundamentals", "analyze_trend", "compare_stocks", "get_summary",
        ]
        for name in expected:
            assert name in names, f"Missing tool: {name}"


class TestSelectToolsForTask:
    def test_us_stock_selects_quote(self):
        result = select_tools_for_task("分析苹果", "AAPL")
        tools = [t[0] for t in result]
        assert "get_quote" in tools

    def test_china_stock_selects_a_share_quote(self):
        result = select_tools_for_task("贵州茅台分析", "600519")
        tools = [t[0] for t in result]
        assert "get_a_share_quote" in tools

    def test_rsi_query_selects_rsi(self):
        result = select_tools_for_task("RSI分析", "AAPL")
        tools = [t[0] for t in result]
        assert "calc_rsi" in tools

    def test_macd_query_selects_macd(self):
        result = select_tools_for_task("MACD指标", "AAPL")
        tools = [t[0] for t in result]
        assert "calc_macd" in tools

    def test_technical_keyword_selects_calc_all(self):
        result = select_tools_for_task("技术分析", "AAPL")
        tools = [t[0] for t in result]
        assert "calc_all" in tools

    def test_fundamentals_keyword_selects_fundamentals(self):
        result = select_tools_for_task("基本面分析", "AAPL")
        tools = [t[0] for t in result]
        assert "get_fundamentals" in tools

    def test_trend_keyword_selects_analyze_trend(self):
        result = select_tools_for_task("趋势分析", "AAPL")
        tools = [t[0] for t in result]
        assert "analyze_trend" in tools

    def test_result_is_list_of_tuples(self):
        result = select_tools_for_task("分析", "AAPL")
        assert isinstance(result, list)
        for item in result:
            assert isinstance(item, tuple)
            assert len(item) == 2
            assert isinstance(item[0], str)
            assert isinstance(item[1], dict)


class TestExecuteTool:
    def test_unknown_tool_returns_error(self):
        result = execute_tool("nonexistent_tool")
        assert "error" in result
        assert "Unknown tool" in result["error"]

    def test_get_quote_returns_dict(self):
        result = execute_tool("get_quote", symbol="AAPL")
        assert isinstance(result, dict)
        # May succeed (has data) or have error (network), but must be dict

    def test_execute_with_kwargs(self):
        result = execute_tool("calc_rsi", symbol="AAPL", period="1mo")
        assert isinstance(result, dict)
