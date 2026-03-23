# CCXT Pro WebSocket 可替换性评估报告（Binance / Gate / MEXC / OKX）

日期：2026-03-23
范围：仅评估当前仓库非 `scripts/sandbox_ccxt_pro` 的生产主链路代码。

## 1. 结论摘要

1. 当前生产链路以 `ccxt` REST 为主，尚未接入 `ccxt.pro` 的交易所 WS（已有 `OKX` 私有 WS 监督器，但未替代核心读写链路）。
2. 可高价值切换到 WS 的接口主要集中在“高频行情与状态”层：
   - `fetch_ticker/fetch_tickers`
   - `fetch_spot_ticker`
   - 部分 `fetch_positions/fetch_balance`（先读 WS，定期 REST 对账）
3. 必须保留 REST 的接口主要是“配置/历史/对账”层：
   - 资金费历史、账单流水、交易费率、杠杆/保证金模式/持仓模式配置
4. 四所综合可迁移度（按当前 `ccxt.pro==4.5.44` 实测）：
   - `OKX`、`Binance`：最高（行情+私有事件+WS下单能力完整）
   - `Gate`：较高（行情+私有事件+WS下单可用）
   - `MEXC`：中等（行情可用，但 `createOrderWs=false`、`watchPositions` 不完整）

## 2. 评估方法与证据

- 代码扫描：生产链路重点文件
  - `/Users/groove/Project/code/crypto/ArbitrageStation/backend/core/exchange_manager/registry.py`
  - `/Users/groove/Project/code/crypto/ArbitrageStation/backend/core/exchange_manager/funding_data.py`
  - `/Users/groove/Project/code/crypto/ArbitrageStation/backend/core/exchange_manager/market_data.py`
  - `/Users/groove/Project/code/crypto/ArbitrageStation/backend/core/exchange_manager/hedge_orders.py`
  - `/Users/groove/Project/code/crypto/ArbitrageStation/backend/core/exchange_manager/order_close.py`
  - `/Users/groove/Project/code/crypto/ArbitrageStation/backend/core/data_collector/funding_collect.py`
  - `/Users/groove/Project/code/crypto/ArbitrageStation/backend/core/data_collector/market_prices.py`
  - `/Users/groove/Project/code/crypto/ArbitrageStation/backend/core/funding_ledger/cursor.py`
  - `/Users/groove/Project/code/crypto/ArbitrageStation/backend/main.py`
  - `/Users/groove/Project/code/crypto/ArbitrageStation/backend/core/okx_private_ws.py`
- 本地库实测：
  - `ccxt==4.5.44`
  - `ccxt.pro==4.5.44`
  - 逐所读取 `exchange.has` 能力矩阵（Binance/Gate/MEXC/OKX）
- 官方文档对照：CCXT Pro 与四所 API 文档（见文末“参考链接”）

## 3. 当前生产链路接口画像（非 sandbox）

### 3.1 高频行情/监控读路径（当前 REST 轮询）

- 行情与价格缓存：`fetch_tickers` / `fetch_ticker` / `fetch_spot_ticker`
  - 来源：`data_collector` 每秒级/秒级调度更新缓存
- 资金费率与成交额：`fetch_funding_rates` / `fetch_funding_rate` / `fetch_tickers`
  - 来源：`collect_funding_rates` 周期任务
- K 线：`fetch_ohlcv` / `fetch_spot_ohlcv`
  - 来源：价差统计、监控 K 线、策略计算

### 3.2 私有账户/交易路径（当前 REST 为主）

- 账户：`fetch_balance`
- 仓位：`fetch_positions` / `fetch_position`
- 下单：`create_order`
- 风控配置：`set_leverage` / `set_margin_mode` / `set_position_mode`
- 交易费率：`fetch_trading_fee`

### 3.3 历史账本/对账路径（当前 REST+原生私有端点）

- `fetch_funding_history` / `fetch_ledger`
- Binance：`fapiPrivateGetIncome`
- OKX：`privateGetAccountBills`
- Gate：`privateFuturesGetSettleAccountBook`
- MEXC：`contractPrivateGetPositionFundingRecords`（通过统一层封装）

## 4. 四所 WS 能力矩阵（基于本地 ccxt.pro 实测）

| 能力（ccxt.pro `has`） | Binance | Gate | MEXC | OKX |
|---|---:|---:|---:|---:|
| `watchTicker` / `watchOrderBook` / `watchTrades` / `watchOHLCV` | ✅ | ✅ | ✅ | ✅ |
| `watchBalance` | ✅ | ✅ | ✅ | ✅ |
| `watchOrders` | ✅ | ✅ | ✅ | ✅ |
| `watchPositions` | ✅ | ✅ | ⚠️(null) | ✅ |
| `watchFundingRate` | ⚠️(null) | ⚠️(null) | ✅ | ✅ |
| `createOrderWs` | ✅ | ✅ | ❌ | ✅ |
| `editOrderWs` | ✅ | ✅ | ❌ | ✅ |
| `cancelOrderWs` | ✅ | ✅ | ❌ | ✅ |
| `fetchBalanceWs` | ✅ | ⚠️(null) | ❌ | ⚠️(null) |
| `fetchPositionsWs` | ✅ | ⚠️(null) | ⚠️(null) | ⚠️(null) |

说明：
- `null` 代表当前版本下未给出统一可用能力声明。
- Binance 虽 `watchFundingRate` 为 `null`，但有 `watchMarkPrice`，其原始字段可带 funding 信息（需交易所特化解析）。

## 5. 接口级“可替换 / 不可替换”报表

| 当前生产接口 | 主要用途 | WS 替换可行性 | 结论 |
|---|---|---|---|
| `fetch_ticker` / `fetch_tickers` / `fetch_spot_ticker` | 快速行情、机会扫描、持仓估值 | 可用 `watchTicker/watchOrderBook` 替代主读路径 | **建议优先迁移** |
| `fetch_ohlcv` / `fetch_spot_ohlcv` | K线统计与回看 | `watchOHLCV` 适合实时增量，不适合历史回填 | **部分替换**（实时用WS，历史保留REST） |
| `fetch_funding_rates` / `fetch_funding_rate` | 资金费率扫描 | OKX/MEXC 可直接 `watchFundingRate`；Binance/Gate 需特化通道/解析 | **分所迁移**（先OKX） |
| `fetch_balance` | 账户概览、可用资金 | 可用 `watchBalance` 事件流 + REST 定时对账 | **建议混合模式** |
| `fetch_positions` / `fetch_position` | 仓位状态、平仓校验 | 可用 `watchPositions`（MEXC 不完整） | **建议混合模式** |
| `create_order` | 下单执行 | Binance/Gate/OKX 可 `createOrderWs`；MEXC 不支持 | **交易核心暂不全量替换**（先保留REST） |
| `set_leverage` / `set_margin_mode` / `set_position_mode` | 风控配置 | 无统一 WS 替代能力 | **必须保留 REST** |
| `fetch_funding_history` / `fetch_ledger` / 交易所私有账单接口 | 历史对账、资金费归档 | 本质是历史分页查询，WS 不适配 | **必须保留 REST** |
| `fetch_trading_fee` | 费率查询 | 无统一 WS 替代 | **保留 REST** |
| `load_markets` | 元数据加载 | 启动阶段元数据拉取仍走 REST | **保留 REST** |

## 6. 按当前项目核心任务的迁移建议

### 阶段 A（高收益、低风险）

目标：减少高频轮询压力，优先替换行情读取。

1. 新建统一 `MarketStreamService`：
   - 订阅 `spot/swap` 的 `ticker + orderbook`
   - 写入现有 `fast_price_cache/spot_fast_price_cache`
2. `update_fast_prices` 改为“读 WS 缓存优先，REST 兜底”。
3. 保留 `fetch_tickers` 低频兜底（例如每 60s 校准）。

### 阶段 B（中收益、中风险）

目标：将账户状态从“请求式”改为“事件式”。

1. 针对 Binance/Gate/OKX 增加私有流：
   - `watchBalance`, `watchOrders`, `watchPositions`
2. Dashboard 与策略读取优先用私有流缓存。
3. 继续保留 REST 对账（例如每 30~60s）防止丢包漂移。

### 阶段 C（可选，高风险）

目标：评估 WS 交易执行。

1. 仅对 Binance/Gate/OKX 做灰度 `createOrderWs`。
2. 下单仍保留 REST fallback（超时/拒绝/断线立即降级）。
3. MEXC 保持 REST 交易执行。

### 长期固定（不迁移）

- 资金费历史归档、账单流水、费率查询、杠杆/保证金/仓位模式设置等均保持 REST。

## 7. 风险与控制

1. 交易所能力不一致：MEXC 的仓位/WS下单能力不完整，必须有 per-exchange 分支。
2. 订单簿一致性：需实现 snapshot+delta 校验、断线重建。
3. 双通道一致性：WS 与 REST 需定期校验，防止静默漂移。
4. 生产安全：交易执行链路建议最后迁移，且默认 REST 主通道不变。

## 8. 执行优先级（建议）

1. **P0**：行情 WS 化（不改交易逻辑）
2. **P1**：账户/仓位事件流 + REST 对账
3. **P2**：资金费率流（先 OKX，再 Binance 特化）
4. **P3**：WS 下单灰度（Binance/Gate/OKX）

---

## 参考链接

- CCXT Pro 手册：<https://github.com/ccxt/ccxt/wiki/ccxt.pro.manual>
- Binance Spot WebSocket Streams：<https://developers.binance.com/docs/binance-spot-api-docs/web-socket-streams>
- Binance Spot WebSocket API Trading：<https://developers.binance.com/docs/binance-spot-api-docs/websocket-api/trading-requests>
- Binance USDⓈ-M Futures WebSocket Market Streams：<https://developers.binance.com/docs/derivatives/usds-margined-futures/websocket-market-streams>
- Binance USDⓈ-M Futures WebSocket New Order：<https://developers.binance.com/docs/derivatives/usds-margined-futures/trade/websocket-api/New-Order>
- Gate Spot WebSocket API（v4）：<https://www.gate.com/docs/developers/apiv4/ws/en/>
- Gate Futures WebSocket API：<https://www.gate.com/docs/developers/futures/ws/en/>
- MEXC Spot v3 API（含 WS 章节）：<https://mexcdevelop.github.io/apidocs/spot_v3_en/>
- MEXC Contract v1 API（含 WS 章节）：<https://mexcdevelop.github.io/apidocs/contract_v1_en/>
- OKX API v5 Docs：<https://app.okx.com/docs-v5/en/>
