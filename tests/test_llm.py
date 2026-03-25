"""Tests for the LLM module."""

import pytest
from src.llm import _build_analysis_prompt


class TestBuildAnalysisPrompt:
    def test_prompt_contains_symbol(self):
        prompt = _build_analysis_prompt("AAPL", "分析苹果", [])
        assert "AAPL" in prompt
        assert "分析苹果" in prompt

    def test_prompt_contains_user_question(self):
        prompt = _build_analysis_prompt("AAPL", "MACD金叉信号", [])
        assert "MACD金叉信号" in prompt

    def test_prompt_with_quote_data(self):
        results = [
            {
                "tool": "get_quote",
                "data": {
                    "symbol": "AAPL",
                    "name": "Apple Inc.",
                    "price": 251.64,
                    "change_pct": 1.2,
                    "high": 254.82,
                    "low": 249.55,
                    "volume": 45000000,
                    "source": "stooq",
                },
                "error": "",
            }
        ]
        prompt = _build_analysis_prompt("AAPL", "分析", results)
        assert "Apple Inc." in prompt
        assert "251.64" in prompt

    def test_prompt_with_fundamentals(self):
        results = [
            {
                "tool": "get_fundamentals",
                "data": {
                    "pe_ratio": 35.2,
                    "eps": 6.57,
                    "market_cap": 3470000000000,
                    "roe": 0.155,
                    "dividend_yield": 0.0044,
                    "recommendation": "buy",
                },
                "error": "",
            }
        ]
        prompt = _build_analysis_prompt("AAPL", "分析", results)
        assert "35.2" in prompt
        assert "6.57" in prompt

    def test_prompt_with_indicators(self):
        results = [
            {
                "tool": "calc_all",
                "data": {
                    "macd": {"macd": -3.93, "signal": -3.64, "histogram": -0.29},
                    "rsi": {"value": 44.24, "signal": "neutral"},
                    "bollinger": {"upper": 262.66, "middle": 238.95, "lower": 215.24, "position_pct": 24.0},
                    "kdj": {"K": 21.02, "D": 18.34, "J": 26.38},
                    "atr": 14.945,
                },
                "error": "",
            }
        ]
        prompt = _build_analysis_prompt("AAPL", "技术分析", results)
        assert "MACD" in prompt
        assert "RSI" in prompt
        assert "布林带" in prompt

    def test_prompt_skips_error_results(self):
        results = [
            {"tool": "get_quote", "data": {}, "error": "Network error"},
        ]
        prompt = _build_analysis_prompt("AAPL", "分析", results)
        # Should not crash, and error data should not appear in formatted sections
        assert "AAPL" in prompt

    def test_prompt_format_is_text(self):
        prompt = _build_analysis_prompt("AAPL", "分析", [])
        assert isinstance(prompt, str)
        assert len(prompt) > 20  # Just check non-empty
