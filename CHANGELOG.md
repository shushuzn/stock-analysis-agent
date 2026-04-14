# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] - 2026-04-14

### Added
- **Test coverage**: New test suites for `agent_tools`, `debate`, and API security
  - `tests/test_agent_tools.py`: ToolCache TTL/clear/miss, CircuitBreaker trips/resets/calls, `select_tools_for_task` keyword routing, akshare ImportError guard
  - `tests/test_debate.py`: `_call_researcher` retry (3 attempts), debate role callables, prompt building, `DEFAULT_MODEL` env support
  - `tests/test_api.py` (`TestApiSecurity`): `_verify_api_key` enumeration prevention, `STOCK_AGENT_API_KEYS` env var required, invalid JSON raises ValueError
- **GitHub Actions CI** (enhanced): 3 parallel jobs — pytest, ruff lint, type check — with pip caching and branch fix (master→main)

### Changed
- **Ruff lint**: Fixed all auto-fixable errors across the codebase (E501, F401, F811, E402, I001, SIM105, UP028, B904, B023, B905, RUF005)
- **Code quality**: Removed hardcoded API keys, fixed asyncio misuse, added retry logic for LLM calls
- **API billing section**: Cleaned up import organization (`import os` moved to top, removed `_json`/`_os` aliases)
- **`analyze_with_debate` return type**: Corrected to `list[dict] | dict` to match actual return value (debate dict or list of tool results)

### Fixed
- **`no-redef` mypy error**: Simplified import pattern with `# type: ignore[no-redef]` on else branch (full-program mode only)
- **Lambda closure issues**: Fixed 6 locations in `agent_tools.py` where loop variable `i` was captured in lambda (Python3 regex `index[i].date()` pattern)
- **Lambda closure in `api.py`**: Fixed `__import__` in lambda causing B023 error
- **Type annotation issues**: Removed `TYPE_CHECKING` block that caused double-definition problems; simplified to two-branch if/else

### Removed
- Tracked `__pycache__`, `.claude`, and garbage files
- Dead code in `agent.py` (importlib import, unnecessary guard, `elif __name__ == "__main__"` block)
- Fullwidth comma in `tests/test_agent.py` line 26

### Security
- API key enumeration prevention: `_verify_api_key` always returns False
- Removed all hardcoded API keys from source code

## [0.1.0] - 2026-04-13

### Added
- Initial release: ReAct stock analysis agent with MCP + FastAPI + Web UI
- Features: bollinger squeeze detection, RSI threshold alerts, token bucket rate limiter
- MiniMax LLM integration for stock analysis
