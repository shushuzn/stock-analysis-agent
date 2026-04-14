"""Tool registry and executor for stock analysis agent.

Uses yfinance for market data — no external API keys required.
Provides: quotes, technical indicators, fundamentals, trend analysis.
"""

from __future__ import annotations

import time
from typing import Any

try:
    import yfinance as yf
    import pandas as pd
    import numpy as np
    YFINANCE_AVAILABLE = True
except ImportError:
    YFINANCE_AVAILABLE = False
    yf = None
    pd = None
    np = None

try:
    from yahooquery import Ticker as YQ_Ticker
    YAHOOQUERY_AVAILABLE = True
except ImportError:
    YAHOOQUERY_AVAILABLE = False
    YQ_Ticker = None


# ── In-Memory Cache (TTL: 5 minutes) ─────────────────────────────────────────

class ToolCache:
    """Simple in-memory cache with TTL."""

    def __init__(self, ttl: int = 300):
        self._cache: dict[str, tuple[float, Any]] = {}
        self._ttl = ttl

    def get(self, key: str) -> Any | None:
        if key in self._cache:
            timestamp, value = self._cache[key]
            if time.time() - timestamp < self._ttl:
                return value
            del self._cache[key]
        return None

    def set(self, key: str, value: Any) -> None:
        self._cache[key] = (time.time(), value)

    def clear(self) -> None:
        self._cache.clear()


_cache = ToolCache(ttl=300)  # 5-minute cache


def _cached(symbol: str, data_type: str) -> dict[str, Any] | None:
    """Get cached data if fresh, else return None."""
    return _cache.get(f"{data_type}:{symbol}")


def _cache_result(symbol: str, data_type: str, result: dict) -> None:
    """Cache successful result."""
    if "error" not in result or not result.get("error"):
        _cache.set(f"{data_type}:{symbol}", result)


# ── Circuit Breaker (Yahoo Finance protection) ──────────────────────────────────

class CircuitBreaker:
    """Trip after N consecutive failures, stay open for a cooldown period."""

    def __init__(self, failure_threshold: int = 3, cooldown: int = 60):
        self._failures = 0
        self._failure_threshold = failure_threshold
        self._cooldown = cooldown
        self._opened_at: float | None = None

    def record_failure(self) -> None:
        self._failures += 1
        if self._failures >= self._failure_threshold:
            self._opened_at = time.time()

    def record_success(self) -> None:
        self._failures = 0
        self._opened_at = None

    @property
    def is_open(self) -> bool:
        if self._opened_at is None:
            return False
        if time.time() - self._opened_at >= self._cooldown:
            # Half-open: allow one probe
            self._opened_at = None
            self._failures = 0
            return False
        return True

    def wait_time(self) -> float:
        if self._opened_at is None:
            return 0
        return max(0, self._cooldown - (time.time() - self._opened_at))


class TokenBucket:
    """Token bucket rate limiter for external API calls."""

    def __init__(self, capacity: int = 10, refill_rate: float = 1.0):
        self._tokens = float(capacity)
        self._capacity = capacity
        self._refill_rate = refill_rate  # tokens per second
        self._last_refill = time.time()

    def _refill(self) -> None:
        now = time.time()
        elapsed = now - self._last_refill
        self._tokens = min(self._capacity, self._tokens + elapsed * self._refill_rate)
        self._last_refill = now

    def acquire(self, cost: int = 1) -> bool:
        self._refill()
        if self._tokens >= cost:
            self._tokens -= cost
            return True
        return False

    def wait_time(self, cost: int = 1) -> float:
        if self._tokens >= cost:
            return 0
        return (cost - self._tokens) / self._refill_rate


_yf_breaker = CircuitBreaker(failure_threshold=3, cooldown=60)
_yf_bucket = TokenBucket(capacity=50, refill_rate=5)  # 50 calls max, refills 5/sec


# ── Quote ────────────────────────────────────────────────────────────────────

def get_quote(symbol: str) -> dict[str, Any]:
    """Get real-time US stock quote via yahooquery (cached 5 min, circuit breaker)."""
    if not YAHOOQUERY_AVAILABLE:
        return {"error": "yahooquery not installed. Run: pip install yahooquery"}

    if _yf_breaker.is_open:
        wait = _yf_breaker.wait_time()
        return {"error": f"Yahoo Finance rate-limited. Retry in {wait:.0f}s.", "symbol": symbol, "source": "yahooquery"}

    if not _yf_bucket.acquire():
        wait = _yf_bucket.wait_time()
        return {"error": f"Yahoo Finance rate limit, retry after {wait:.1f}s.", "symbol": symbol, "source": "yahooquery", "rate_limited": True}

    cached = _cached(symbol, "quote")
    if cached is not None:
        _yf_breaker.record_success()
        return cached

    try:
        ticker = YQ_Ticker(symbol)
        price_data = ticker.price.get(symbol, {})

        if not price_data or "regularMarketPrice" not in price_data:
            _yf_breaker.record_failure()
            return {"error": f"No price data for {symbol}", "symbol": symbol}

        p = price_data
        price = p.get("regularMarketPrice")
        change = p.get("regularMarketChangePercent")

        _yf_breaker.record_success()
        result = {
            "symbol": symbol,
            "name": p.get("longName") or p.get("shortName", symbol),
            "price": price,
            "change_pct": round(change * 100, 2) if isinstance(change, (int, float)) else None,
            "change_abs": round(p.get("regularMarketChange", 0), 2),
            "open": p.get("regularMarketOpen"),
            "high": p.get("regularMarketDayHigh"),
            "low": p.get("regularMarketDayLow"),
            "volume": p.get("regularMarketVolume"),
            "market_cap": p.get("marketCap"),
            "pe_ratio": None,
            "eps": None,
            "year52_high": None,
            "year52_low": None,
            "exchange": p.get("exchange"),
            "currency": p.get("currency", "USD"),
            "source": "yahooquery",
        }
        _cache_result(symbol, "quote", result)
        return result
    except Exception as e:
        _yf_breaker.record_failure()
        return {"error": f"Failed to fetch quote for {symbol}: {e}", "symbol": symbol}


def get_a_share_quote(symbol: str) -> dict[str, Any]:
    """Get China A-share quote via yahooquery (cached 5 min, circuit breaker)."""
    if not YAHOOQUERY_AVAILABLE:
        return {"error": "yahooquery not installed. Run: pip install yahooquery"}

    if _yf_breaker.is_open:
        wait = _yf_breaker.wait_time()
        return {"error": f"Yahoo Finance rate-limited. Retry in {wait:.0f}s.", "symbol": symbol, "source": "yahooquery"}

    cached = _cached(symbol, "a_share")
    if cached is not None:
        _yf_breaker.record_success()
        return cached

    suffix = ".SS" if symbol.startswith("6") else ".SZ"
    yq_symbol = f"{symbol}{suffix}"

    try:
        ticker = YQ_Ticker(yq_symbol)
        price_data = ticker.price.get(yq_symbol, {})

        if not price_data or "regularMarketPrice" not in price_data:
            _yf_breaker.record_failure()
            return {"error": f"No price data for {symbol}", "symbol": symbol}

        p = price_data
        price = p.get("regularMarketPrice")
        change = p.get("regularMarketChangePercent")

        _yf_breaker.record_success()
        result = {
            "symbol": symbol,
            "name": p.get("longName") or p.get("shortName", symbol),
            "price": price,
            "change_pct": round(change * 100, 2) if isinstance(change, (int, float)) else None,
            "change_abs": round(p.get("regularMarketChange", 0), 2),
            "open": p.get("regularMarketOpen"),
            "high": p.get("regularMarketDayHigh"),
            "low": p.get("regularMarketDayLow"),
            "volume": p.get("regularMarketVolume"),
            "market_cap": p.get("marketCap"),
            "pe": None,
            "pb": None,
            "year52_high": None,
            "year52_low": None,
            "source": "yahooquery",
        }
        _cache_result(symbol, "a_share", result)
        return result
    except Exception as e:
        _yf_breaker.record_failure()
        return {"error": f"Failed to fetch A-share quote for {symbol}: {e}", "symbol": symbol}


# ── Technical Indicators ───────────────────────────────────────────────────────

def _get_historical_data(symbol: str, period: str = "6mo") -> pd.DataFrame | None:
    """Get historical price data as DataFrame via yahooquery."""
    if not YAHOOQUERY_AVAILABLE:
        return None
    try:
        ticker = YQ_Ticker(symbol)
        df = ticker.history(period=period)
        if df.empty:
            df = ticker.history(period="3mo")
        # yahooquery may return MultiIndex (symbol, date) — reset to flatten
        if isinstance(df.index, pd.MultiIndex):
            df = df.reset_index(level=0)
        # ensure date column exists and is datetime
        if "date" not in df.columns and isinstance(df.index, pd.DatetimeIndex):
            df = df.reset_index()
        if "date" in df.columns:
            df["date"] = pd.to_datetime(df["date"])
            df = df.set_index("date")
        # yahooquery returns lowercase columns, capitalize for compatibility
        df.columns = [c.capitalize() for c in df.columns]
        return df
    except Exception:
        return None


def _compute_rsi(prices: pd.Series, period: int = 14) -> dict[str, Any]:
    """Compute RSI indicator."""
    delta = prices.diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    current = rsi.iloc[-1] if not rsi.empty else None

    signal = "overbought" if current and current > 70 else "oversold" if current and current < 30 else "neutral"
    return {"current": round(current, 2) if current else None, "signal": signal}


def _compute_macd(prices: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> dict[str, Any]:
    """Compute MACD indicator."""
    exp1 = prices.ewm(span=fast, adjust=False).mean()
    exp2 = prices.ewm(span=slow, adjust=False).mean()
    macd_line = exp1 - exp2
    signal_line = macd_line.ewm(span=signal, adjust=False).mean()
    histogram = macd_line - signal_line

    # Count crossovers
    crossovers = []
    for i in range(1, len(macd_line)):
        prev_macd, curr_macd = macd_line.iloc[i-1], macd_line.iloc[i]
        prev_sig, curr_sig = signal_line.iloc[i-1], signal_line.iloc[i]
        if prev_macd < prev_sig and curr_macd > curr_sig:
            crossovers.append({"date": str(getattr(macd_line.index[i], 'date', lambda: macd_line.index[i])()), "type": "golden_cross"})
        elif prev_macd > prev_sig and curr_macd < curr_sig:
            crossovers.append({"date": str(getattr(macd_line.index[i], 'date', lambda: macd_line.index[i])()), "type": "death_cross"})

    return {
        "current": {
            "macd": round(macd_line.iloc[-1], 4),
            "signal": round(signal_line.iloc[-1], 4),
            "histogram": round(histogram.iloc[-1], 4),
        },
        "count": len(crossovers),
        "crossovers": crossovers[-5:],  # Last 5 crossovers
    }


def _compute_bollinger(prices: pd.Series, period: int = 20) -> dict[str, Any]:
    """Compute Bollinger Bands."""
    sma = prices.rolling(window=period).mean()
    std = prices.rolling(window=period).std()
    upper = sma + (2 * std)
    lower = sma - (2 * std)
    current = prices.iloc[-1]
    position = ((current - lower.iloc[-1]) / (upper.iloc[-1] - lower.iloc[-1])) * 100 if upper.iloc[-1] != lower.iloc[-1] else 50

    signal = "overbought" if position > 80 else "oversold" if position < 20 else "neutral"
    return {
        "current": {
            "upper": round(upper.iloc[-1], 2),
            "middle": round(sma.iloc[-1], 2),
            "lower": round(lower.iloc[-1], 2),
            "close": round(current, 2),
            "position_pct": round(position, 1),
        },
        "signal": signal,
    }


def _compute_kdj(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 9) -> dict[str, Any]:
    """Compute KDJ indicator."""
    lowest_low = low.rolling(window=period).min()
    highest_high = high.rolling(window=period).max()
    rsv = (close - lowest_low) / (highest_high - lowest_low) * 100
    k = rsv.ewm(com=2, adjust=False).mean()
    d = k.ewm(com=2, adjust=False).mean()
    j = 3 * k - 2 * d

    crossovers = []
    for i in range(1, len(k)):
        if k.iloc[i-1] < d.iloc[i-1] and k.iloc[i] > d.iloc[i]:
            crossovers.append({"date": str(getattr(k.index[i], 'date', lambda: k.index[i])()), "type": "golden_cross"})
        elif k.iloc[i-1] > d.iloc[i-1] and k.iloc[i] < d.iloc[i]:
            crossovers.append({"date": str(getattr(k.index[i], 'date', lambda: k.index[i])()), "type": "death_cross"})

    return {
        "current": {
            "K": round(k.iloc[-1], 2),
            "D": round(d.iloc[-1], 2),
            "J": round(j.iloc[-1], 2),
        },
        "crossovers": crossovers[-5:],
    }


def _compute_atr(high: pd.Series, low: pd.Series, close: pd.Series, period: int = 14) -> float:
    """Compute Average True Range."""
    tr1 = high - low
    tr2 = (high - close.shift()).abs()
    tr3 = (low - close.shift()).abs()
    tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
    atr = tr.rolling(window=period).mean()
    return round(atr.iloc[-1], 4) if not atr.empty else None


def calc_rsi(symbol: str, period: str = "6mo") -> dict[str, Any]:
    """Calculate RSI."""
    if not YFINANCE_AVAILABLE:
        return {"error": "yfinance not installed"}

    df = _get_historical_data(symbol, period)
    if df is None or df.empty:
        return {"error": f"No data for {symbol}", "current": None}

    result = _compute_rsi(df["Close"])
    return result


def check_rsi_threshold(symbol: str, threshold: float = 30, period: str = "6mo") -> dict[str, Any]:
    """Check if RSI is below (oversold) or above (overbought) a custom threshold."""
    if not YFINANCE_AVAILABLE:
        return {"error": "yfinance not installed"}

    df = _get_historical_data(symbol, period)
    if df is None or df.empty:
        return {"error": f"No data for {symbol}"}

    result = _compute_rsi(df["Close"])
    current = result.get("current")
    if current is None:
        return {"error": "RSI calculation failed"}

    oversold = current < threshold
    return {
        "symbol": symbol,
        "rsi": current,
        "threshold": threshold,
        "is_oversold": oversold,
        "signal": "oversold" if oversold else "neutral",
    }


def calc_macd(symbol: str, period: str = "6mo") -> dict[str, Any]:
    """Calculate MACD."""
    if not YFINANCE_AVAILABLE:
        return {"error": "yfinance not installed"}

    df = _get_historical_data(symbol, period)
    if df is None or df.empty:
        return {"error": f"No data for {symbol}"}

    return _compute_macd(df["Close"])


def calc_bollinger(symbol: str, period: str = "6mo") -> dict[str, Any]:
    """Calculate Bollinger Bands."""
    if not YFINANCE_AVAILABLE:
        return {"error": "yfinance not installed"}

    df = _get_historical_data(symbol, period)
    if df is None or df.empty:
        return {"error": f"No data for {symbol}"}

    return _compute_bollinger(df["Close"])


def calc_bollinger_squeeze(symbol: str, period: str = "6mo", lookback: int = 120, percentile: float = 20) -> dict[str, Any]:
    """Detect Bollinger Band squeeze (bandwidth contraction).

    Returns current bandwidth and its historical percentile rank.
    When bandwidth falls below `percentile`th historical percentile, it signals
    a potential volatility expansion setup.
    """
    if not YFINANCE_AVAILABLE:
        return {"error": "yfinance not installed"}

    df = _get_historical_data(symbol, period)
    if df is None or df.empty:
        return {"error": f"No data for {symbol}"}

    close = df["Close"]
    if len(close) < lookback:
        lookback = max(10, len(close) // 2)

    sma = close.rolling(window=20).mean()
    std = close.rolling(window=20).std()
    upper = sma + (2 * std)
    lower = sma - (2 * std)
    bandwidth = (upper - lower) / sma * 100

    current_bw = bandwidth.iloc[-1]
    hist_bw = bandwidth.dropna().iloc[-lookback:]

    if len(hist_bw) < 2:
        return {"error": f"Not enough data for percentile calculation (need {lookback})"}

    pct_rank = (hist_bw < current_bw).sum() / len(hist_bw) * 100
    is_squeeze = pct_rank <= percentile

    return {
        "bandwidth": round(current_bw, 4),
        "percentile_rank": round(pct_rank, 1),
        "is_squeeze": is_squeeze,
        "threshold": round(hist_bw.quantile(percentile / 100), 4),
        "signal": "squeeze" if is_squeeze else "normal",
    }


def calc_kdj(symbol: str, period: str = "6mo") -> dict[str, Any]:
    """Calculate KDJ."""
    if not YFINANCE_AVAILABLE:
        return {"error": "yfinance not installed"}

    df = _get_historical_data(symbol, period)
    if df is None or df.empty:
        return {"error": f"No data for {symbol}"}

    return _compute_kdj(df["High"], df["Low"], df["Close"])


def calc_atr(symbol: str, period: str = "6mo") -> dict[str, Any]:
    """Calculate ATR."""
    if not YFINANCE_AVAILABLE:
        return {"error": "yfinance not installed"}

    df = _get_historical_data(symbol, period)
    if df is None or df.empty:
        return {"error": f"No data for {symbol}"}

    return {"current": _compute_atr(df["High"], df["Low"], df["Close"])}


def calc_all(symbol: str, period: str = "6mo") -> dict[str, Any]:
    """Calculate all technical indicators at once (cached 5 min)."""
    if not YFINANCE_AVAILABLE:
        return {"error": "yfinance not installed"}

    # Check cache first
    cached = _cached(symbol, "calc_all")
    if cached is not None:
        return cached

    df = _get_historical_data(symbol, period)
    if df is None or df.empty:
        return {"error": f"No data for {symbol}"}

    close = df["Close"]
    result = {
        "rsi": _compute_rsi(close),
        "macd": _compute_macd(close),
        "bollinger": _compute_bollinger(close),
        "kdj": _compute_kdj(df["High"], df["Low"], close),
        "atr": _compute_atr(df["High"], df["Low"], close),
    }
    _cache_result(symbol, "calc_all", result)
    return result


# ── Fundamentals ───────────────────────────────────────────────────────────────

def get_fundamentals(symbol: str) -> dict[str, Any]:
    """Get fundamental data via yahooquery (cached 5 min, circuit breaker)."""
    if not YAHOOQUERY_AVAILABLE:
        return {"error": "yahooquery not installed. Run: pip install yahooquery"}

    if _yf_breaker.is_open:
        wait = _yf_breaker.wait_time()
        return {"error": f"Yahoo Finance rate-limited. Retry in {wait:.0f}s.", "symbol": symbol}

    cached = _cached(symbol, "fundamentals")
    if cached is not None:
        _yf_breaker.record_success()
        return cached

    try:
        ticker = YQ_Ticker(symbol)
        def _safe_dict(v):
            return v if isinstance(v, dict) else {}

        sd = _safe_dict(ticker.summary_detail.get(symbol, {}))
        fd = _safe_dict(ticker.financial_data.get(symbol, {}))
        ks = _safe_dict(ticker.key_stats.get(symbol, {}))
        _price = ticker.price.get(symbol, {})
        price = _safe_dict(_price)

        _yf_breaker.record_success()
        result = {
            "symbol": symbol,
            "name": price.get("longName") or price.get("shortName", symbol),
            "pe_ratio": sd.get("trailingPE"),
            "eps": None,  # Not available in yahooquery free tier
            "market_cap": price.get("marketCap"),
            "revenue": None,
            "net_income": None,
            "roe": None,
            "debt_to_equity": None,
            "dividend_yield": ks.get("dividendYield"),
            "beta": ks.get("beta"),
            "recommendation": fd.get("recommendationKey", "N/A"),
            "52w_high": sd.get("fiftyTwoWeekHigh"),
            "52w_low": sd.get("fiftyTwoWeekLow"),
            "source": "yahooquery",
        }
        _cache_result(symbol, "fundamentals", result)
        return result
    except Exception as e:
        _yf_breaker.record_failure()
        return {"error": f"Failed to fetch fundamentals for {symbol}: {e}"}


# ── Trend Analysis ─────────────────────────────────────────────────────────────

def analyze_trend(symbol: str, period: str = "6mo") -> dict[str, Any]:
    """Analyze trend using MA crossovers (cached 5 min, circuit breaker)."""
    if not YFINANCE_AVAILABLE:
        return {"error": "yfinance not installed"}

    if _yf_breaker.is_open:
        wait = _yf_breaker.wait_time()
        return {"error": f"Yahoo Finance rate-limited. Retry in {wait:.0f}s.", "symbol": symbol}

    cached = _cached(symbol, "trend")
    if cached is not None:
        _yf_breaker.record_success()
        return cached

    df = _get_historical_data(symbol, period)
    if df is None or df.empty:
        _yf_breaker.record_failure()
        return {"error": f"No data for {symbol}"}

    close = df["Close"]
    ma5 = close.rolling(window=5).mean()
    ma20 = close.rolling(window=20).mean()
    ma60 = close.rolling(window=60).mean()

    # Current values
    current_ma5 = ma5.iloc[-1]
    current_ma20 = ma20.iloc[-1]
    current_ma60 = ma60.iloc[-60] if len(ma60) >= 60 else ma60.iloc[-1]

    # Determine trend
    if current_ma5 > current_ma20 > current_ma60:
        trend = "上升趋势"
        strength = "强"
    elif current_ma5 < current_ma20 < current_ma60:
        trend = "下降趋势"
        strength = "强"
    elif current_ma5 > current_ma20:
        trend = "短期上升"
        strength = "中"
    elif current_ma5 < current_ma20:
        trend = "短期下降"
        strength = "中"
    else:
        trend = "震荡"
        strength = "弱"

    # MA crossovers
    crossovers = []
    for i in range(max(5, len(ma5) - 60), len(ma5)):
        if ma5.iloc[i-1] < ma20.iloc[i-1] and ma5.iloc[i] > ma20.iloc[i]:
            crossovers.append({"date": str(getattr(ma5.index[i], 'date', lambda: ma5.index[i])()), "type": "golden_cross", "ma_type": "MA5/MA20"})
        elif ma5.iloc[i-1] > ma20.iloc[i-1] and ma5.iloc[i] < ma20.iloc[i]:
            crossovers.append({"date": str(getattr(ma5.index[i], 'date', lambda: ma5.index[i])()), "type": "death_cross", "ma_type": "MA5/MA20"})

    _yf_breaker.record_success()
    result = {
        "trend": trend,
        "strength": strength,
        "ma5": round(current_ma5, 2) if current_ma5 else None,
        "ma20": round(current_ma20, 2) if current_ma20 else None,
        "ma60": round(current_ma60, 2) if current_ma60 else None,
        "signals": crossovers[-5:],
    }
    _cache_result(symbol, "trend", result)
    return result


# ── Multi-Timeframe Resonance ─────────────────────────────────────────────────

def analyze_multi_timeframe(symbol: str) -> dict[str, Any]:
    """Analyze symbol across daily/weekly/monthly timeframes. Returns resonance signals."""
    if not YFINANCE_AVAILABLE:
        return {"error": "yfinance not installed"}

    periods = {
        "daily": "1mo",
        "weekly": "3mo",
        "monthly": "6mo",
    }

    results = {}
    for label, period in periods.items():
        df = _get_historical_data(symbol, period)
        if df is None or df.empty:
            results[label] = {"error": f"No data for {period}"}
            continue

        close = df["Close"]
        ma5 = close.rolling(window=5).mean()
        ma20 = close.rolling(window=20).mean()

        current_ma5 = ma5.iloc[-1]
        current_ma20 = ma20.iloc[-1]

        if current_ma5 > current_ma20:
            trend = "上升"
        elif current_ma5 < current_ma20:
            trend = "下降"
        else:
            trend = "震荡"

        results[label] = {
            "trend": trend,
            "ma5": round(current_ma5, 2) if current_ma5 else None,
            "ma20": round(current_ma20, 2) if current_ma20 else None,
        }

    # Resonance: count how many timeframes agree
    trends = [r.get("trend") for r in results.values() if "error" not in r]
    bullish_count = sum(1 for t in trends if t == "上升")
    bearish_count = sum(1 for t in trends if t == "下降")

    if bullish_count >= 3:
        resonance = "强共振-看涨"
    elif bearish_count >= 3:
        resonance = "强共振-看跌"
    elif bullish_count == 2:
        resonance = "弱共振-看涨"
    elif bearish_count == 2:
        resonance = "弱共振-看跌"
    else:
        resonance = "无共振"

    return {
        "symbol": symbol,
        "resonance": resonance,
        "timeframes": results,
    }


# ── A股板块轮动 ────────────────────────────────────────────────────────────────

def get_sector_rotation(indicator: str = "概念", limit: int = 20) -> dict[str, Any]:
    """Get A-share sector rotation data via AKShare.

    Args:
        indicator: 新浪行业/启明星行业/概念/地域/行业
        limit: number of top sectors to return (by absolute gain)
    """
    try:
        import akshare as ak
    except ImportError:
        return {"error": "akshare 未安装，请运行: pip install akshare"}

    try:
        df = ak.stock_sector_spot(indicator=indicator)
        if df is None or df.empty:
            return {"error": "No sector data returned"}

        # Sort by 涨跌幅 descending
        df = df.sort_values("涨跌幅", ascending=False)

        top_gainers = df.head(limit)[["板块", "涨跌幅", "涨跌额", "总成交量", "总成交额"]].to_dict("records")
        top_losers = df.tail(limit)[["板块", "涨跌幅", "涨跌额", "总成交量", "总成交额"]].to_dict("records")

        return {
            "indicator": indicator,
            "top_gainers": top_gainers,
            "top_losers": top_losers,
            "total_sectors": len(df),
        }
    except Exception as e:
        return {"error": str(e)}


# ── Summary ───────────────────────────────────────────────────────────────────

def get_summary(symbol: str, period: str = "6mo") -> dict[str, Any]:
    """Get full stock summary combining quote, indicators, and trend (cached 5 min)."""
    if not YFINANCE_AVAILABLE:
        return {"error": "yfinance not installed"}

    # Check cache first
    cached = _cached(symbol, "summary")
    if cached is not None:
        return cached

    quote = get_quote(symbol)
    if "error" in quote:
        return quote

    indicators = calc_all(symbol, period)
    trend = analyze_trend(symbol, period)

    # Generate signal
    rsi_val = indicators.get("rsi", {}).get("current")
    macd_hist = indicators.get("macd", {}).get("current", {}).get("histogram")

    signal = "neutral"
    if rsi_val and macd_hist:
        if rsi_val < 30 and macd_hist > 0:
            signal = "超跌反弹信号"
        elif rsi_val > 70 and macd_hist < 0:
            signal = "超买信号"
        elif macd_hist > 0:
            signal = "偏多"
        else:
            signal = "偏空"

    result = {
        "name": quote.get("name", symbol),
        "symbol": symbol,
        "current_price": quote.get("price"),
        "change_pct": quote.get("change_pct"),
        "trend": trend.get("trend", "N/A"),
        "signal": signal,
        "indicators": {
            "rsi": rsi_val,
            "rsi_signal": indicators.get("rsi", {}).get("signal"),
            "macd": macd_hist,
        },
    }
    _cache_result(symbol, "summary", result)
    return result


def compare_stocks(symbols: str | list, period: str = "6mo") -> dict[str, Any]:
    """Compare multiple stocks."""
    if not YFINANCE_AVAILABLE:
        return {"error": "yfinance not installed"}

    if isinstance(symbols, str):
        symbols = symbols.split(",")

    results = {}
    for symbol in symbols:
        symbol = symbol.strip()
        df = _get_historical_data(symbol, period)
        if df is None or df.empty:
            results[symbol] = {"error": f"No data for {symbol}"}
            continue

        # Calculate metrics
        returns = df["Close"].pct_change().dropna()
        sharpe = returns.mean() / returns.std() * (252 ** 0.5) if returns.std() > 0 else 0
        max_drawdown = (df["Close"] / df["Close"].cummax() - 1).min()
        volatility = returns.std() * (252 ** 0.5)

        results[symbol] = {
            "sharpe_ratio": round(sharpe, 2),
            "max_drawdown": round(max_drawdown, 2),
            "volatility": round(volatility, 2),
        }

    return results


# ── Backtest ─────────────────────────────────────────────────────────────────

def backtest_signal(symbol: str, days: int = 365) -> dict[str, Any]:
    """Backtest RSI+MACD signal accuracy against historical price data.

    Simulates: buy when bull signal, sell when bear signal.
    Returns win rate, total return, and per-signal stats.
    """
    if not YAHOOQUERY_AVAILABLE:
        return {"error": "yahooquery not installed. Run: pip install yahooquery"}

    try:
        ticker = YQ_Ticker(symbol)
        # yahooquery: history() returns a DataFrame with date index
        df = ticker.history(period=f"{days}d")
    except Exception as e:
        return {"error": str(e)}

    if df is None or df.empty:
        return {"error": f"No price data for {symbol}"}

    # Ensure we have a 'Close' column (yahooquery uses lowercase)
    if "Close" not in df.columns and "close" in df.columns:
        df = df.rename(columns={"close": "Close", "high": "High", "low": "Low", "open": "Open", "volume": "Volume"})
    if "Close" not in df.columns:
        return {"error": f"No Close column in returned data for {symbol}"}

    if len(df) < 60:
        return {"error": f"Insufficient data: {len(df)} rows"}

    close = df["Close"]

    # Compute RSI and MACD on full series
    delta = close.diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss.replace(0, 1e-10)
    rsi = 100 - (100 / (1 + rs))

    exp1 = close.ewm(span=12, adjust=False).mean()
    exp2 = close.ewm(span=26, adjust=False).mean()
    macd_line = exp1 - exp2
    signal_line = macd_line.ewm(span=9, adjust=False).mean()
    macd_hist = macd_line - signal_line

    # Generate daily signals
    signals = []
    for i in range(30, len(df)):
        r = rsi.iloc[i]
        m = macd_hist.iloc[i]
        if r and m:
            if r < 30 and m > 0:
                signals.append(("bull", close.iloc[i]))
            elif r > 70 and m < 0:
                signals.append(("bear", close.iloc[i]))

    if len(signals) < 2:
        return {"error": f"Too few signals generated: {len(signals)}", "total_signals": len(signals)}

    # Simulate trades
    trades = []
    for i in range(1, len(signals)):
        prev_sig, prev_price = signals[i - 1]
        curr_sig, curr_price = signals[i]
        ret = (curr_price - prev_price) / prev_price
        trades.append({
            "entry": prev_sig,
            "exit": curr_sig,
            "entry_price": round(prev_price, 2),
            "exit_price": round(curr_price, 2),
            "return_pct": round(ret * 100, 2),
            "profitable": ret > 0,
        })

    winners = [t for t in trades if t["profitable"]]
    total_ret = sum(t["return_pct"] for t in trades)

    return {
        "symbol": symbol,
        "days": days,
        "total_signals": len(signals),
        "total_trades": len(trades),
        "win_rate": round(len(winners) / len(trades) * 100, 1) if trades else 0,
        "total_return_pct": round(total_ret, 2),
        "avg_return_pct": round(total_ret / len(trades), 2) if trades else 0,
        "bull_trades": len([t for t in trades if t["entry"] == "bull"]),
        "bear_trades": len([t for t in trades if t["entry"] == "bear"]),
    }


# ── Tool Registry (for compatibility) ────────────────────────────────────────

TOOLS = {
    "get_quote": {"fn": get_quote, "desc": "Get US stock quote", "args": {"symbol": "str"}},
    "get_a_share_quote": {"fn": get_a_share_quote, "desc": "Get China A-share quote", "args": {"symbol": "str"}},
    "calc_rsi": {"fn": calc_rsi, "desc": "Calculate RSI", "args": {"symbol": "str", "period": "str"}},
    "check_rsi_threshold": {"fn": check_rsi_threshold, "desc": "Check if RSI crosses custom threshold", "args": {"symbol": "str", "threshold": "float", "period": "str"}},
    "calc_macd": {"fn": calc_macd, "desc": "Calculate MACD", "args": {"symbol": "str", "period": "str"}},
    "calc_bollinger": {"fn": calc_bollinger, "desc": "Calculate Bollinger Bands", "args": {"symbol": "str", "period": "str"}},
    "calc_bollinger_squeeze": {"fn": calc_bollinger_squeeze, "desc": "Detect Bollinger Band squeeze (bandwidth contraction)", "args": {"symbol": "str", "period": "str", "lookback": "int", "percentile": "float"}},
    "calc_kdj": {"fn": calc_kdj, "desc": "Calculate KDJ", "args": {"symbol": "str", "period": "str"}},
    "calc_atr": {"fn": calc_atr, "desc": "Calculate ATR", "args": {"symbol": "str", "period": "str"}},
    "calc_all": {"fn": calc_all, "desc": "Calculate all indicators", "args": {"symbol": "str", "period": "str"}},
    "get_fundamentals": {"fn": get_fundamentals, "desc": "Get fundamental data", "args": {"symbol": "str"}},
    "analyze_trend": {"fn": analyze_trend, "desc": "Analyze MA trend", "args": {"symbol": "str", "period": "str"}},
    "compare_stocks": {"fn": compare_stocks, "desc": "Compare stocks", "args": {"symbols": "list[str]", "period": "str"}},
    "get_summary": {"fn": get_summary, "desc": "Get summary", "args": {"symbol": "str", "period": "str"}},
    "analyze_multi_timeframe": {"fn": analyze_multi_timeframe, "desc": "Analyze multi-timeframe resonance (daily/weekly/monthly)", "args": {"symbol": "str"}},
    "get_sector_rotation": {"fn": get_sector_rotation, "desc": "Get A-share sector rotation data (top gainers/losers)", "args": {"indicator": "str", "limit": "int"}},
}


def list_tools() -> list[dict]:
    """Return all available tools."""
    return [{"name": name, "desc": info["desc"], "args": info["args"]} for name, info in TOOLS.items()]


def execute_tool(name: str, **kwargs) -> dict[str, Any]:
    """Execute a tool by name."""
    if name not in TOOLS:
        return {"error": f"Unknown tool: {name}"}
    return TOOLS[name]["fn"](**kwargs)


# ── Tool Selection Strategy ───────────────────────────────────────────────────

def select_tools_for_task(task: str, symbol: str) -> list[tuple[str, dict]]:
    """Select appropriate tools based on task."""
    task_lower = task.lower()
    selections = []

    # Quote always first
    if symbol.isdigit() and len(symbol) == 6:
        selections.append(("get_a_share_quote", {"symbol": symbol}))
    else:
        selections.append(("get_quote", {"symbol": symbol}))

    # Fundamentals
    if any(kw in task_lower for kw in [
        "基本面", "估值", "财务", "fundamental", "invest", "分析", "报告",
        "pe", "p/e", "eps", "市盈率", "每股收益", "股价", "盈利", "收入", "利润",
        "revenue", "profit", "earnings", "dividend", "dividends",
        "market cap", "capitalization", "市值",
    ]):
        selections.append(("get_fundamentals", {"symbol": symbol}))

    # Technical indicators
    if any(kw in task_lower for kw in ["技术", "趋势", "指标", "technical", "trend", "rsi", "macd", "波动"]):
        selections.append(("calc_all", {"symbol": symbol}))

    # Specific indicators
    if "rsi" in task_lower:
        selections.append(("calc_rsi", {"symbol": symbol}))
    if "macd" in task_lower:
        selections.append(("calc_macd", {"symbol": symbol}))
    if "kdj" in task_lower:
        selections.append(("calc_kdj", {"symbol": symbol}))
    if "atr" in task_lower or "波动" in task_lower:
        selections.append(("calc_atr", {"symbol": symbol}))
    if "布林" in task_lower or "bollinger" in task_lower:
        selections.append(("calc_bollinger", {"symbol": symbol}))
    if "收口" in task_lower or "squeeze" in task_lower:
        selections.append(("calc_bollinger_squeeze", {"symbol": symbol}))

    # Trend
    if any(kw in task_lower for kw in ["趋势", "均线", "ma", "trend", "交叉"]):
        selections.append(("analyze_trend", {"symbol": symbol}))

    # Multi-timeframe
    if any(kw in task_lower for kw in ["共振", "多周期", "多时间", "timeframe", "time frame"]):
        selections.append(("analyze_multi_timeframe", {"symbol": symbol}))

    # Default: full analysis
    if len(selections) == 1:
        selections.append(("calc_all", {"symbol": symbol}))
        selections.append(("get_fundamentals", {"symbol": symbol}))

    return selections
