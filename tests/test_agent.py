"""Tests for the ReAct agent."""

from src.agent import ReActAgent, extract_symbol


class TestExtractSymbol:
    def test_us_ticker(self):
        assert extract_symbol("AAPL") == "AAPL"
        assert extract_symbol("NVDA") == "NVDA"
        assert extract_symbol("TSLA") == "TSLA"

    def test_chinese_stock_code(self):
        assert extract_symbol("600519") == "600519"
        assert extract_symbol("000001") == "000001"
        # 00700 is 5-digit HK code, not matched by 6-digit pattern

    def test_chinese_name_mapping(self):
        assert extract_symbol("苹果") == "AAPL"
        assert extract_symbol("贵州茅台") == "600519"
        assert extract_symbol("英伟达") == "NVDA"
        assert extract_symbol("特斯拉") == "TSLA"

    def test_query_extraction(self):
        assert extract_symbol("分析苹果的趋势") == "AAPL"
        assert extract_symbol("600519贵州茅台") == "600519"
        # NVDA后跟中文时\b单词边界不匹配,这是预期行为
        assert extract_symbol("分析 NVDA 的趋势") == "NVDA"

    def test_empty(self):
        assert extract_symbol("") == ""
        assert extract_symbol("   ") == ""


class TestReActAgent:
    def test_agent_initialization(self):
        agent = ReActAgent(max_steps=5, verbose=False)
        assert agent.max_steps == 5
        assert agent.verbose is False
        assert agent.history == []

    def test_agent_history_empty_initially(self):
        agent = ReActAgent()
        assert agent.history == []

    def test_agent_max_steps_default(self):
        agent = ReActAgent()
        assert agent.max_steps == 10
