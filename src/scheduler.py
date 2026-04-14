"""Background scheduler for automatic watchlist analysis at market close."""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from .agent import ReActAgent
from .persistence import store_analysis
from .report import format_report
from .watchlist import get_all as wl_get_all


def _load_config() -> dict[str, Any]:
    config_path = Path.home() / ".stock-analysis-agent" / "config.json"
    if config_path.exists():
        try:
            return json.loads(config_path.read_text())
        except Exception:
            pass
    return {}


class Scheduler:
    """Run watchlist analysis on a schedule (no external deps, stdlib only)."""

    def __init__(self, interval_minutes: int = 60):
        self._interval = interval_minutes * 60
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._enabled = False

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self._enabled = True

    def stop(self) -> None:
        self._stop.set()
        self._enabled = False

    def _run(self) -> None:
        while not self._stop.wait(self._interval):
            self._tick()

    def _tick(self) -> None:
        cfg = _load_config()
        if not cfg.get("auto_analyze", False):
            return

        symbols = wl_get_all().get("symbols", [])
        if not symbols:
            return

        period = cfg.get("auto_analyze_period", "1mo")
        results = []

        for sym in symbols:
            try:
                agent = ReActAgent(max_steps=6, verbose=False)
                r = agent.analyze(f"{sym}技术分析", sym)
                results.append(r)
                store_analysis(sym, f"{sym}技术分析", period, "data", None, format_report(sym, f"{sym}技术分析", r), r, True)
            except Exception:
                pass

        # Push notification if configured
        sckey = cfg.get("serverchan_sckey") or cfg.get("sckey")
        if sckey and results:
            try:
                import urllib.parse
                import urllib.request
                summary = f"📊 自动分析完成 ({len(results)}只股票)"
                url = f"https://wxpusher.zjiecode.com/api/send/message/?appToken={sckey}&content={urllib.parse.quote(summary)}&contentType=1"
                req = urllib.request.Request(url, headers={"User-Agent": "StockAnalysisAgent/1.0"})
                urllib.request.urlopen(req, timeout=5)
            except Exception:
                pass

    def trigger_now(self) -> dict[str, Any]:
        """Manually trigger a scheduled run."""
        self._tick()
        return {"success": True, "message": "Scheduled analysis triggered"}


_scheduler = Scheduler()


def start_scheduler(interval_minutes: int = 60) -> None:
    _scheduler.start()


def stop_scheduler() -> None:
    _scheduler.stop()


def trigger_scheduled_run() -> dict[str, Any]:
    return _scheduler.trigger_now()
