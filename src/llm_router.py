"""Multi-Tier LLM Router.

Three-tier fallback chain:
  1. MiniMax API   — high quality, paid, low latency
  2. Ollama        — free, local, medium latency
  3. Local model   — free, offline, higher latency

Routing logic:
  - Complexity score = text_length / 500 + keywords_heavy * 2
  - tier >= 3 → local; tier == 2 → Ollama; tier == 1 → MiniMax
  - On failure: automatic fallback to next tier
"""

from __future__ import annotations

import os
import textwrap
from dataclasses import dataclass, field
from enum import Enum
from typing import Generator

import anthropic

# ── Cost tracking ────────────────────────────────────────────────────────────


@dataclass
class CostTracker:
    """Track LLM spend per provider."""

    minimax_calls: int = 0
    minimax_tokens: int = 0
    ollama_calls: int = 0
    local_calls: int = 0

    def report(self) -> str:
        return (
            f"MiniMax: {self.minimax_calls} calls, ~{self.minimax_tokens} tokens\n"
            f"Ollama:  {self.ollama_calls} calls\n"
            f"Local:   {self.local_calls} calls"
        )


# ── Provider enum ────────────────────────────────────────────────────────────


class LLMProvider(Enum):
    MINIMAX = "minimax"
    OLLAMA = "ollama"
    LOCAL = "local"


# ── Complexity triage ─────────────────────────────────────────────────────────


def _query_complexity(query: str, results: list[dict]) -> int:
    """Return 1-3 (1=high quality needed, 3=local OK).

    Higher text content = more complex = higher tier number.
    """
    text_len = len(query)
    # Count heavy analytical keywords
    heavy = any(
        k in query
        for k in [
            "宏观",
            "行业",
            "估值",
            "对比",
            "预测",
            "风险",
            "财报",
            "分红",
            "并购",
            "竞争",
        ]
    )
    score = text_len / 500 + (2 if heavy else 0)
    if score >= 3:
        return 3  # local / Ollama
    if score >= 1.5:
        return 2  # Ollama
    return 1  # MiniMax


# ── Ollama client ────────────────────────────────────────────────────────────


def _ollama_complete(
    model: str,
    messages: list[dict],
    system: str | None = None,
    max_tokens: int = 1024,
) -> str:
    """Call local Ollama API."""
    import urllib.request

    ollama_base = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")

    payload = {
        "model": model,
        "messages": (
            [{"role": "system", "content": system}, *messages]
            if system
            else messages
        ),
        "stream": False,
        "options": {"num_predict": max_tokens},
    }

    data = __import__("json").dumps(payload).encode()
    req = urllib.request.Request(
        f"{ollama_base}/api/chat",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        result = __import__("json").loads(resp.read())
    return result["message"]["content"]


# ── Local model via MiniMax-compatible endpoint ───────────────────────────────


def _local_complete(
    model: str,
    messages: list[dict],
    system: str | None = None,
    max_tokens: int = 512,
) -> str:
    """Call local MiniMax-compatible endpoint (e.g. lmstudio, ollama with openai compat)."""
    import urllib.request

    base = os.environ.get(
        "LOCAL_LLM_BASE_URL", "http://localhost:8080"
    )
    api_key = os.environ.get("LOCAL_LLM_API_KEY", "local")

    payload = {
        "model": model,
        "messages": (
            [{"role": "system", "content": system}, *messages]
            if system
            else messages
        ),
        "max_tokens": max_tokens,
        "temperature": 0.3,
    }

    data = __import__("json").dumps(payload).encode()
    req = urllib.request.Request(
        f"{base}/v1/chat/completions",
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=120) as resp:
        result = __import__("json").loads(resp.read())
    return result["choices"][0]["message"]["content"]


# ── Main router ──────────────────────────────────────────────────────────────


@dataclass
class LLMResult:
    text: str
    provider: LLMProvider
    fallback_used: bool = False


@dataclass
class LLMRouter:
    """Multi-tier router with automatic fallback."""

    # Minimi provider settings
    minimax_api_key: str | None = None
    minimax_base_url: str = "https://api.minimaxi.com/anthropic"
    minimax_model: str = os.environ.get("ANTHROPIC_MODEL", "MiniMax-M2.7")

    # Ollama settings
    ollama_model: str = "llama3.2:1b"
    ollama_timeout: int = 60

    # Local settings
    local_model: str = "local-model"
    local_timeout: int = 120

    # Behavior
    force_provider: LLMProvider | None = None
    cost_tracker: CostTracker = field(default_factory=CostTracker)

    def _build_messages(
        self, prompt: str, system: str | None
    ) -> list[dict]:
        msgs = []
        if system:
            msgs.append({"role": "system", "content": system})
        msgs.append({"role": "user", "content": prompt})
        return msgs

    def _call_minimax(
        self, prompt: str, system: str, max_tokens: int
    ) -> str:
        client = anthropic.Anthropic(
            api_key=self.minimax_api_key
            or os.environ.get(
                "ANTHROPIC_API_KEY",
                "",
            ),
            base_url=self.minimax_base_url,
        )
        response = client.messages.create(
            model=self.minimax_model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        )
        for block in response.content:
            if hasattr(block, "type") and block.type == "text":
                self.cost_tracker.minimax_calls += 1
                self.cost_tracker.minimax_tokens += response.usage.output_tokens if hasattr(response, "usage") else 0
                return block.text
        return str(response.content)

    def complete(self, prompt: str, system: str | None = None, max_tokens: int = 1024) -> LLMResult:
        """Single-shot complete with automatic fallback."""
        if self.force_provider:
            tier = {"minimax": 1, "ollama": 2, "local": 3}[self.force_provider.value]
        else:
            tier = _query_complexity(prompt, [])

        tried: list[LLMProvider] = []
        errors: list[str] = []

        # Try in order based on tier
        for attempt_tier in [max(1, tier - 1), tier, min(3, tier + 1)]:
            if attempt_tier == 1:
                provider = LLMProvider.MINIMAX
            elif attempt_tier == 2:
                provider = LLMProvider.OLLAMA
            else:
                provider = LLMProvider.LOCAL

            if provider in tried:
                continue
            tried.append(provider)

            try:
                if provider == LLMProvider.MINIMAX:
                    text = self._call_minimax(prompt, system or "", max_tokens)
                    return LLMResult(text=text, provider=provider, fallback_used=len(tried) > 1)
                elif provider == LLMProvider.OLLAMA:
                    text = _ollama_complete(
                        self.ollama_model,
                        self._build_messages(prompt, system),
                        system=system,
                        max_tokens=max_tokens,
                    )
                    self.cost_tracker.ollama_calls += 1
                    return LLMResult(text=text, provider=provider, fallback_used=len(tried) > 1)
                else:
                    text = _local_complete(
                        self.local_model,
                        self._build_messages(prompt, system),
                        system=system,
                        max_tokens=max_tokens,
                    )
                    self.cost_tracker.local_calls += 1
                    return LLMResult(text=text, provider=provider, fallback_used=len(tried) > 1)
            except Exception as e:
                errors.append(f"{provider.value}: {e}")
                continue

        # All failed
        return LLMResult(
            text=f"[LLM调用全部失败: {'; '.join(errors)}]",
            provider=LLMProvider.MINIMAX,
            fallback_used=False,
        )


# ── Module-level singleton ────────────────────────────────────────────────────


_router: LLMRouter | None = None


def get_router() -> LLMRouter:
    global _router
    if _router is None:
        _router = LLMRouter(
            force_provider=_parse_force_provider(),
        )
    return _router


def _parse_force_provider() -> LLMProvider | None:
    env = os.environ.get("LLM_FORCE_PROVIDER", "").lower()
    if env == "minimax":
        return LLMProvider.MINIMAX
    if env == "ollama":
        return LLMProvider.OLLAMA
    if env == "local":
        return LLMProvider.LOCAL
    return None


# ── Backward-compatible wrappers ─────────────────────────────────────────────


def analyze_with_llm(symbol: str, query: str, results: list[dict]) -> str:
    """Generate LLM-powered analysis — now with multi-tier routing."""
    from .llm import _build_analysis_prompt

    prompt = _build_analysis_prompt(symbol, query, results)
    system = textwrap.dedent(
        """\
        你是一位资深股票投资分析师，有十年以上的A股和美股分析经验。
        你的分析必须：
        1. 解释技术指标背后的投资逻辑（RSI>70为什么是超买、MACD金叉为什么看涨）
        2. 结合基本面和技术面给出综合判断
        3. 用中文回答，语言简洁专业
        4. 给出明确的买卖信号和风险提示
        5. 提及具体的价格点位和指标数值作为依据
        不要泛泛而谈，每个结论都要有数据支撑。
    """
    )

    router = get_router()
    result = router.complete(prompt, system=system, max_tokens=1024)

    # Log which provider was used
    if result.fallback_used:
        print(f"[LLM Router: fell back to {result.provider.value}]")

    return result.text


def analyze_with_llm_streaming(
    symbol: str, query: str, results: list[dict]
) -> Generator[str, None, None]:
    """Streaming — currently delegates to non-streaming (Ollama streaming not used)."""
    # Streaming is only supported on MiniMax in this implementation
    from .llm import _build_analysis_prompt

    prompt = _build_analysis_prompt(symbol, query, results)
    system = textwrap.dedent(
        """\
        你是一位资深股票投资分析师，有十年以上的A股和美股分析经验。
        你的分析必须：
        1. 解释技术指标背后的投资逻辑
        2. 结合基本面和技术面给出综合判断
        3. 用中文回答，语言简洁专业
        4. 给出明确的买卖信号和风险提示
    """
    )

    try:
        client = anthropic.Anthropic(
            api_key=os.environ.get(
                "ANTHROPIC_API_KEY",
                "",
            ),
            base_url=os.environ.get(
                "ANTHROPIC_BASE_URL",
                "https://api.minimaxi.com/anthropic",
            ),
        )
        with client.messages.stream(
            model=os.environ.get("ANTHROPIC_MODEL", "MiniMax-M2.7"),
            max_tokens=1024,
            system=system,
            messages=[{"role": "user", "content": prompt}],
        ) as stream:
            for text in stream.text_stream:
                yield text
    except Exception as e:
        yield f"[LLM分析失败: {e}]"
