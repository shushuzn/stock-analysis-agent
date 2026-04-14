# Stock Analysis Agent — APIaaS 商业化文档

> 最后更新：2026-04-07

## 计费模式

**按调用次数计费（Pay-per-Call）**：每次辩论分析调用计费一次，无订阅费。

| 套餐 | 单价 | 说明 |
|------|------|------|
| 免费额度 | 0 | 每月前 10 次调用 |
| 标准 | $0.10 / 次 | 超出部分，按次计费 |
| 企业定制 | 面议 | 专属模型、私有部署、 SLA 保障 |

## APIaaS 核心端点

### 辩论分析（多模型对比）
```
POST /debate/analyze
Content-Type: application/json
X-API-Key: your-api-key

{
  "api_key": "sk-demo",
  "query": "分析苹果股票近期走势",
  "symbol": "AAPL",
  "period": "6mo"
}
```

**响应：**
```json
{
  "symbol": "AAPL",
  "query": "分析苹果股票近期走势",
  "period": "6mo",
  "analysis": {
    "bull": "看多方分析...",
    "bear": "看空方分析...",
    "synthesis": "综合结论..."
  },
  "mode": "debate",
  "models": ["bull", "bear", "synthesis"]
}
```

### 账单查询
```
GET /billing
```

**响应：**
```json
{
  "requests": 42,
  "total_calls": 42,
  "models_used": {"debate": 42},
  "plan": "per_call",
  "price_per_call_usd": 0.10,
  "estimated_cost_usd": 4.20
}
```

## 差异化竞争力

- **三路 LLM 对比**：Bull / Bear / Synthesis 多角度辩论分析
- **多模型路由**：MiniMax / Ollama / Local 三级降级
- **A 股支持**：AKShare 实时数据，支持 A 股代码
- **技术指标**：RSI / MACD / Bollinger Bands / KD指标

## 目标客户

- **券商**：投研报告自动化生成
- **私募**：快速多角度股票分析
- **量化社群**：信号提取与策略回测
