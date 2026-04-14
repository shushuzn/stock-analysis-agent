# Stock Analysis Agent

ReAct-based AI agent for stock market analysis. Takes natural language queries and produces comprehensive investment analysis reports.

## Architecture

```
Query: "分析苹果最近趋势"
         │
         ▼
  ┌─────────────┐
  │  ReAct Agent │  ← select tools → execute → observe → repeat
  └─────────────┘
         │
         ▼
  Tool Executor
    ├── get_quote          (real-time price)
    ├── calc_all           (RSI/MACD/Bollinger/KDJ/ATR)
    ├── get_fundamentals   (P/E, EPS, market cap)
    └── analyze_trend      (MA crossovers)
         │
         ▼
  Report Generator → 📊 Analysis Report
```

## Three Interfaces

| Interface | Command | Best For |
|----------|---------|----------|
| **Web UI** | Open `index.html` in browser | Non-technical users |
| **CLI** | `stock-agent "苹果技术分析"` | Terminal workflow |
| **HTTP API** | `POST /analyze` | Integration with other tools |

## Quick Start

```bash
# 1. Start API server
cd stock-analysis-agent
pip install fastapi
python run.py
# Server runs on http://localhost:8001

# 2. Open web UI
# Just open index.html in your browser

# 3. CLI usage
stock-agent "苹果技术分析"
stock-agent "贵州茅台" -s 600519
stock-agent "NVDA RSI MACD" -v
stock-agent --list-tools
```

## Web UI

Open `index.html` directly in a browser — no build step required.

Features:
- Natural language input (English or Chinese)
- US stocks (AAPL, NVDA, TSLA) and China A-shares (600519, 000001)
- Color-coded trading signals
- Dark theme

## HTTP API

```bash
# Health check
curl http://localhost:8001/

# List tools
curl http://localhost:8001/tools

# Analyze (blocking)
curl -X POST http://localhost:8001/analyze \
  -H "Content-Type: application/json" \
  -d '{"query":"苹果技术分析","symbol":"AAPL","period":"6mo"}'

# Analyze (streaming)
curl -X POST http://localhost:8001/analyze \
  -H "Content-Type: application/json" \
  -d '{"query":"AAPL analysis","symbol":"AAPL","stream":true}'
```

## Examples

| Query | Symbol | Description |
|-------|--------|-------------|
| `苹果技术分析` | AAPL | Full technical analysis |
| `贵州茅台RSI` | 600519 | RSI indicator only |
| `NVDA趋势分析` | NVDA | Trend with MA crossovers |
| `AAPL 基本面` | AAPL | Fundamental data |
| `苹果 vs 微软` | AAPL+MSFT | Use compare API |

## CLI Flags

```bash
python -m src.cli QUERY [-s SYMBOL] [-v] [--list-tools] [--period PERIOD] [-f FORMAT] [-w SECONDS] [--debate] [--max-rounds N]
```

| Flag | Description |
|------|-------------|
| `query` | Natural language query (e.g. "分析苹果趋势") |
| `-s, --symbol` | Stock symbol (auto-detected if omitted) |
| `-v, --verbose` | Show agent reasoning steps |
| `--list-tools` | List all available tools |
| `--period` | Historical period: 1mo/3mo/6mo/1y/2y (default: 6mo) |
| `-f, --format` | Output format: text/json (default: text) |
| `-w, --watch SECONDS` | Auto-refresh every N seconds |
| `--debate` | Enable multi-agent bull/bear debate |
| `--max-rounds N` | Number of debate rounds (default: 2) |

## Requirements

- Python 3.10+
- pandas, requests, fastapi, uvicorn
- stock-analysis-mcp (sibling project, auto-imported via path)
