"""Tests for the report generator."""

from src.report import _fmt_market_cap, _fmt_vol, _generate_signal, format_report


class TestFmtVol:
    def test_billions(self):
        assert _fmt_vol(1_500_000_000) == "1.50B"
        assert _fmt_vol(2_000_000_000) == "2.00B"

    def test_millions(self):
        assert _fmt_vol(45_000_000) == "45.00M"
        assert _fmt_vol(1_000_000) == "1.00M"

    def test_thousands(self):
        assert _fmt_vol(1500) == "1.5K"
        assert _fmt_vol(999) == "999"

    def test_zero(self):
        assert _fmt_vol(0) == "0"


class TestFmtMarketCap:
    def test_trillions(self):
        result = _fmt_market_cap(3_470_000_000_000)
        assert "$3.47T" in result

    def test_billions(self):
        result = _fmt_market_cap(347_000_000_000)
        assert "$347.00B" in result

    def test_millions(self):
        result = _fmt_market_cap(176_000_000)
        assert "$176.00M" in result

    def test_non_numeric(self):
        assert _fmt_market_cap("N/A") == "N/A"
        assert _fmt_market_cap(None) == "None"


class TestGenerateSignal:
    def test_empty_results(self):
        result = _generate_signal([])
        assert result == ""

    def test_bullish_rsi_oversold(self):
        results = [
            {"tool": "calc_rsi", "data": {"current": 25, "signal": "oversold"}}
        ]
        result = _generate_signal(results)
        assert "偏多" in result or "看涨" in result

    def test_bearish_rsi_overbought(self):
        results = [
            {"tool": "calc_rsi", "data": {"current": 85, "signal": "overbought"}}
        ]
        result = _generate_signal(results)
        assert "偏空" in result or "看跌" in result

    def test_neutral_rsi(self):
        results = [
            {"tool": "calc_rsi", "data": {"current": 50, "signal": "neutral"}}
        ]
        result = _generate_signal(results)
        assert "中性" in result or "neutral" in result.lower()


class TestFormatReport:
    def test_report_contains_symbol(self):
        results = []
        report = format_report("AAPL", "分析苹果", results)
        assert "AAPL" in report

    def test_report_contains_query(self):
        results = []
        report = format_report("AAPL", "分析苹果", results)
        assert "分析苹果" in report

    def test_report_format_structure(self):
        results = []
        report = format_report("AAPL", "分析", results)
        lines = report.split("\n")
        assert any("股票分析报告" in line for line in lines)
        assert any("=" in line for line in lines)

    def test_report_with_quote_data(self):
        results = [
            {
                "tool": "get_quote",
                "data": {
                    "symbol": "AAPL",
                    "name": "APPLE INC",
                    "price": 251.64,
                    "open": 250.35,
                    "high": 254.82,
                    "low": 249.55,
                    "volume": 45000000,
                    "source": "stooq",
                },
                "error": "",
                "observation": "APPLE INC价格$251.64",
            }
        ]
        report = format_report("AAPL", "报价查询", results)
        assert "AAPL" in report
        assert "APPLE INC" in report
        assert "251.64" in report

    def test_report_with_error(self):
        results = [
            {"tool": "get_quote", "data": {}, "error": "No data available", "observation": ""}
        ]
        report = format_report("INVALID", "分析", results)
        assert "错误" in report or "error" in report.lower()

    def test_report_with_a_share_quote(self):
        results = [
            {
                "tool": "get_a_share_quote",
                "data": {
                    "symbol": "600519",
                    "name": "贵州茅台",
                    "price": 1408.81,
                    "change_pct": 0.11,
                    "volume": 1573500,
                    "source": "tencent",
                },
                "error": "",
                "observation": "贵州茅台价格¥1408.81",
            }
        ]
        report = format_report("600519", "A股分析", results)
        assert "600519" in report
        assert "贵州茅台" in report
        assert "1408.81" in report
