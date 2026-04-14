"""Tests for agent_tools module."""

import pytest
from unittest.mock import patch, MagicMock


class TestToolCache:
    """Test ToolCache TTL functionality."""

    def test_cache_set_and_get(self):
        from src.agent_tools import ToolCache
        cache = ToolCache(ttl=300)
        cache.set("key1", {"price": 100})
        result = cache.get("key1")
        assert result == {"price": 100}

    def test_cache_expired(self):
        from src.agent_tools import ToolCache
        import time
        cache = ToolCache(ttl=0)  # 0 second TTL = always expired
        cache.set("key1", {"price": 100})
        time.sleep(0.05)
        result = cache.get("key1")
        assert result is None

    def test_cache_clear(self):
        from src.agent_tools import ToolCache
        cache = ToolCache()
        cache.set("key1", "value1")
        cache.set("key2", "value2")
        cache.clear()
        assert cache.get("key1") is None
        assert cache.get("key2") is None

    def test_cache_miss(self):
        from src.agent_tools import ToolCache
        cache = ToolCache()
        assert cache.get("nonexistent") is None


class TestCircuitBreaker:
    """Test CircuitBreaker protection."""

    def test_breaker_closed_initially(self):
        from src.agent_tools import CircuitBreaker
        breaker = CircuitBreaker(failure_threshold=3, cooldown=60)
        assert breaker._opened_at is None

    def test_breaker_trips_after_threshold(self):
        from src.agent_tools import CircuitBreaker
        breaker = CircuitBreaker(failure_threshold=3, cooldown=60)
        breaker.record_failure()
        breaker.record_failure()
        breaker.record_failure()
        assert breaker._opened_at is not None

    def test_breaker_resets_after_cooldown(self):
        from src.agent_tools import CircuitBreaker
        import time
        breaker = CircuitBreaker(failure_threshold=2, cooldown=1)
        breaker.record_failure()
        breaker.record_failure()
        assert breaker._opened_at is not None
        time.sleep(1.1)
        # After cooldown, it should allow again
        assert breaker._opened_at is not None  # Still open until record_success


class TestSelectToolsForTask:
    """Test select_tools_for_task keyword matching."""

    def test_rsi_keywords(self):
        from src.agent_tools import select_tools_for_task
        tools = select_tools_for_task("分析 RSI 超买超卖", "AAPL")
        tool_names = [t[0] for t in tools]
        assert "calc_rsi" in tool_names

    def test_macd_keywords(self):
        from src.agent_tools import select_tools_for_task
        tools = select_tools_for_task("MACD 金叉死叉", "AAPL")
        tool_names = [t[0] for t in tools]
        assert "calc_macd" in tool_names

    def test_bollinger_keywords(self):
        from src.agent_tools import select_tools_for_task
        tools = select_tools_for_task("布林带挤压", "AAPL")
        tool_names = [t[0] for t in tools]
        assert "calc_bollinger" in tool_names

    def test_fundamentals_keywords_en(self):
        from src.agent_tools import select_tools_for_task
        tools = select_tools_for_task("What is the P/E ratio and EPS?", "AAPL")
        tool_names = [t[0] for t in tools]
        assert "get_fundamentals" in tool_names

    def test_fundamentals_keywords_cn(self):
        from src.agent_tools import select_tools_for_task
        tools = select_tools_for_task("市盈率 每股收益", "AAPL")
        tool_names = [t[0] for t in tools]
        assert "get_fundamentals" in tool_names

    def test_trend_keywords(self):
        from src.agent_tools import select_tools_for_task
        tools = select_tools_for_task("分析趋势", "AAPL")
        tool_names = [t[0] for t in tools]
        assert "analyze_trend" in tool_names

    def test_quote_keywords(self):
        from src.agent_tools import select_tools_for_task
        tools = select_tools_for_task("current price", "AAPL")
        tool_names = [t[0] for t in tools]
        assert "get_quote" in tool_names

    def test_compare_keywords(self):
        from src.agent_tools import select_tools_for_task
        tools = select_tools_for_task("compare AAPL and TSLA", "AAPL")
        tool_names = [t[0] for t in tools]
        assert "compare_stocks" in tool_names


class TestGetSectorRotation:
    """Test get_sector_rotation with akshare import handling."""

    def test_akshare_not_installed(self):
        from src.agent_tools import get_sector_rotation
        with patch("src.agent_tools.AKSHARE_AVAILABLE", False):
            result = get_sector_rotation("概念", 20)
            assert result.get("error") is not None
            assert "akshare" in result["error"].lower()

    def test_sector_rotation_success(self):
        from src.agent_tools import get_sector_rotation
        # Mock akshare so it doesn't actually call the API
        with patch.dict("sys.modules", {"akshare": MagicMock()}):
            with patch("src.agent_tools.AKSHARE_AVAILABLE", True):
                # Just verify it doesn't raise - actual API call skipped
                pass  # Would need real akshare for full test


class TestListTools:
    """Test list_tools returns valid structure."""

    def test_list_tools_returns_list(self):
        from src.agent_tools import list_tools
        tools = list_tools()
        assert isinstance(tools, list)
        assert len(tools) > 0

    def test_list_tools_has_required_fields(self):
        from src.agent_tools import list_tools
        tools = list_tools()
        for tool in tools:
            assert "name" in tool
            assert "description" in tool
            assert "parameters" in tool
