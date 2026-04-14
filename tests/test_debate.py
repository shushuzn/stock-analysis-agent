"""Tests for debate module."""

import pytest
from unittest.mock import patch, MagicMock


class TestDebateRetryLogic:
    """Test debate retry mechanism."""

    def test_call_researcher_retries_on_failure(self):
        from src.debate import _call_researcher
        with patch("src.debate._call_llm") as mock_llm:
            # First two calls fail, third succeeds
            mock_llm.side_effect = [Exception("fail1"), Exception("fail2"), "success"]
            result = _call_researcher("system", "prompt", max_tokens=512)
            assert result == "success"
            assert mock_llm.call_count == 3

    def test_call_researcher_exhausts_retries(self):
        from src.debate import _call_researcher
        with patch("src.debate._call_llm") as mock_llm:
            mock_llm.side_effect = Exception("always fail")
            with pytest.raises(Exception):
                _call_researcher("system", "prompt", max_tokens=512)
            # Should have tried 3 times (1 initial + 2 retries)
            assert mock_llm.call_count == 3


class TestDebateRoles:
    """Test debate role functions exist and are callable."""

    def test_bull_researcher_callable(self):
        from src.debate import bull_researcher
        # Just verify it's callable and has correct signature
        assert callable(bull_researcher)

    def test_bear_researcher_callable(self):
        from src.debate import bear_researcher
        assert callable(bear_researcher)

    def test_run_debate_callable(self):
        from src.debate import run_debate
        assert callable(run_debate)


class TestBuildResearcherPrompt:
    """Test prompt building for researchers."""

    def test_build_researcher_prompt_returns_string(self):
        from src.debate import _build_researcher_prompt
        prompt = _build_researcher_prompt(
            role="bull",
            symbol="AAPL",
            query="趋势如何",
            analyst_results=[{"name": "get_quote", "result": {"price": 150}}],
        )
        assert isinstance(prompt, str)
        assert "AAPL" in prompt


class TestDebateDefaultModel:
    """Test DEFAULT_MODEL environment variable support."""

    def test_default_model_from_env(self):
        from src.debate import DEFAULT_MODEL
        # Should be "MiniMax-M2.7" or env-override
        assert isinstance(DEFAULT_MODEL, str)
        assert len(DEFAULT_MODEL) > 0
