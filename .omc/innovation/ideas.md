# Idea Pool — stock-analysis-agent

> Stage: 💡 active | 📋 proposed | 🔬 running | 📦 shipped | 💀 killed | ⏸️ dormant

## Ideas

- [2026-04-05] 📦 历史回测验证 — backtest_signal(symbol, days=365)函数，模拟金叉/死叉买入持有，计算总收益率和胜率 | expected_benefit: 提升报告可信度，避免"看起来准但实际无效"的指标 | reason: signal已有评分逻辑，直接用yfinance历史数据跑一遍即可，pandas计算 | score: 2x3=6 | [brainstorm] | status: shipped
  - approach: agent_tools.py新增backtest_signal(symbol, days=365)函数，模拟金叉/死叉买入持有，计算总收益率和胜率

- [2026-04-05] 💡 分析结果持久化 — 将每次分析结果存SQLite，支持按股票、时间、signal类型查询历史 | expected_benefit: 积累数据支撑回测和趋势判断 | reason: SQLite是Python内置库（sqlite3），无需安装额外依赖 | score: 2x3=6 | [brainstorm] | status: shipped
  - approach: src/persistence.py用sqlite3建表(store_analysis)，analyze后自动写入，api.py新增/history和/stats端点

- [2026-04-05] 💡 Web UI dark/light主题切换 — index.html加主题切换按钮，CSS变量切换 | expected_benefit: 改善用户体验，夜晚交易时段护眼 | reason: 纯前端CSS变量改动，10分钟可完成 | score: 2x3=6 | [brainstorm] | status: shipped
  - approach: index.html加toggle按钮，document.body.dataset.theme切换，CSS定义两套颜色变量

- [2026-04-05] 💡 流式输出美化 — streaming模式下SSE逐字输出而非整块刷新，前端打字机效果 | expected_benefit: 提升体验，实时看到分析进展 | reason: 后端已是SSE流式，前端只需改eventSource处理逻辑，逐行追加显示 | score: 2x3=6 | [brainstorm] | status: shipped
  - approach: index.html改用onmessage逐行追加，添加打字机CSS动画，streaming时不disable输入框

- [2026-04-05] 📦 分析完成微信/钉钉通知 — POST /notify端点，ServerChan(wxpusher)推送，SCKEY从body或config.json读取 | expected_benefit: 用户无需盯屏，报告出来后自动收到 | reason: 已有serverchan推送经验，requests.post一行代码，5分钟可完成 | score: 2x3=6 | [brainstorm] | status: shipped
  - approach: api.py新增POST /notify端点（需用户提供SCKEY），analyze完成后自动POST到wxpusher

- [2026-04-05] 📦 多股票横向对比视图 — GET /compare端点+⚡对比按钮，前端输入逗号分隔股票，表格展示夏普比率/最大回撤/波动率 | expected_benefit: 便于横向选股对比 | reason: API已有compare_stocks tool，前端加批量输入框，后端循环调用返回对比数据 | score: 2x3=6 | [brainstorm] | status: shipped
  - approach: index.html输入框支持"NVDA,AAPL,TSLA"格式，后端拆分symbol后并发执行tool，结果聚合返回并排表格

- [2026-04-05] 📦 持仓模拟器 — src/portfolio.py管理持仓（buy/sell/get_position），GET/POST /portfolio端点，前端💼按钮+持仓面板展示盈亏 | expected_benefit: 不真钱验证策略有效性，积累交易记录支撑回测 | reason: 复用backtest_signal和compare_stocks，数据模型一致，实现路径最短 | score: 4x3=12 | [brainstorm] | status: shipped
  - approach: src/portfolio.py管理持仓列表（symbol/数量/成本价），买入卖出操作，当前盈亏计算；前端加持仓面板展示

- [2026-04-05] 📦 语音价格播报 — src/tts.py (Windows SAPI) + POST /tts端点，预警触发时自动TTS播报，enable_tts配置开关 | expected_benefit: 解放视觉，无需盯盘 | reason: Windows原生TTS，无需安装依赖，PowerShell一行调用 | score: 3x2=6 | [brainstorm] | status: shipped
  - approach: 前端监控页面展示自选股实时价格，后台定时轮询check，触发预警调用/notify

- [2026-04-05] 📦 PDF报告导出 — src/export_pdf.py生成PDF，GET /export端点，📄PDF导出按钮触发下载 | expected_benefit: 便于分享报告给其他人，存档记录 | reason: Python reportlab库生成PDF，前端加导出按钮 | score: 3x3=9 | [brainstorm] | status: shipped

- [2026-04-05] 📦 布林带收口识别 — 识别Bandwidth低于历史N%分位，预警波动率收缩后的突破机会 | expected_benefit: 补充波动率维度，提升信号质量 | reason: agent_tools已有_compute_bollinger，扩展即可 | score: 2x2=4 | [brainstorm] | status: shipped
- [2026-04-05] 📦 RSI超跌策略模板 — 一键设置RSI<30超跌信号监控，支持自定义阈值和持仓周期 | expected_benefit: 降低策略使用门槛，无需手动配置指标 | reason: agent_tools已有_calc_rsi，前端加参数面板 | score: 2x2=4 | [brainstorm] | status: shipped
- [2026-04-05] 📦 API限流保护层 — 外部数据请求层增加令牌桶限流，防止触发免费API上游限制 | expected_benefit: 提升稳定性，避免半夜推送中断 | reason: CircuitBreaker已存在，扩展为令牌桶 | score: 2x2=4 | [brainstorm] | status: shipped
- [2026-04-05] 📦 分析历史回放 — 从SQLite读取历史分析记录，支持按时间/symbol回放报告 | expected_benefit: 回顾历史判断，验证策略一致性 | reason: persistence已有get_history，前端加时间线面板 | score: 2x2=4 | [brainstorm] | status: shipped
