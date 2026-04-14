"""Tests for debate module."""

from unittest.mock import MagicMock, patch


class TestDebateRetryLogic:
    """Test debate retry mechanism — _call_researcher calls _get_client()."""

    def test_call_researcher_retries_on_failure(self):
        """First two API calls fail, third succeeds."""
        from src.debate import _call_researcher

        mock_response = MagicMock()
        mock_response.content = [MagicMock(type="text", text="success")]

        with patch("src.debate._get_client") as mock_get_client:
            mock_client = MagicMock()
            # First two raise, third returns valid response
            mock_client.messages.create.side_effect = [
                Exception("fail1"),
                Exception("fail2"),
                mock_response,
            ]
            mock_get_client.return_value = mock_client

            result = _call_researcher("system", "prompt", max_tokens=512)
            assert result == "success"
            assert mock_client.messages.create.call_count == 3

class TestDebateRetryExhausted:
    """Separate class so mock patch is fresh — no call count accumulation."""

    def test_call_researcher_exhausts_retries(self):
        """All attempts fail, returns error string after MAX_RETRIES."""
        from src.debate import MAX_RETRIES, _call_researcher

        with patch("src.debate._get_client") as mock_get_client:
            mock_get_client.return_value.messages.create.side_effect = Exception("always fail")
            result = _call_researcher("sys", "prompt")
            assert result.startswith("[研究员分析失败:")
            assert "always fail" in result
            assert mock_get_client.return_value.messages.create.call_count == MAX_RETRIES + 1


class TestDebateRoles:
    """Test debate role functions exist and are callable."""

    def test_bull_researcher_callable(self):
        from src.debate import bull_researcher

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
            symbol="AAPL",
            query="趋势如何",
            analyst_results=[{"name": "get_quote", "result": {"price": 150}}],
            stance="bullish",
        )
        assert isinstance(prompt, str)
        assert "AAPL" in prompt


class TestDebateDefaultModel:
    """Test DEFAULT_MODEL environment variable support."""

    def test_default_model_from_env(self):
        from src.debate import DEFAULT_MODEL

        assert isinstance(DEFAULT_MODEL, str)
        assert len(DEFAULT_MODEL) > 0
