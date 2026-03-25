# 主产品线 CCXT 接口清单（2026-03-25）

> 目标：只回答“主产品线到底调用了哪些 CCXT 交易所接口”。
> 范围：`backend/`，不含 `scripts/sandbox_ccxt_pro/`。

## 1) 最终接口名清单（去重）

### 1.1 通用市场/账户/交易接口
- `fetch_ticker`
- `fetch_tickers`
- `fetch_ohlcv`
- `fetch_funding_rate`
- `fetch_funding_rates`
- `fetch_funding_history`
- `fetch_funding_rate_history`
- `fetch_balance`
- `fetch_positions`
- `fetch_position`
- `fetch_ledger`
- `fetch_trading_fee`
- `create_order`
- `set_leverage`
- `set_margin_mode`
- `set_position_mode`

### 1.2 交易所私有/原生接口（CCXT raw endpoints）
- `privateGetAccount`
- `privateGetAccountBills`
- `privateGetV5AccountTransactionLog`
- `privateFuturesGetSettleAccountBook`
- `contractPrivateGetPositionFundingRecords`
- `fapiPrivateGetIncome`
- `fapiPrivateGetLeverageBracket`
- `fapiPrivatePostMarginType`
- `fapiPrivate_post_positionside_dual`
- `private_post_account_set_position_mode`
- `private_post_v5_position_switch_mode`

### 1.3 交易参数与市场元数据接口
- `load_markets`
- `load_time_difference`
- `market`
- `amount_to_precision`
- `cost_to_precision`
- `create_market_buy_order_with_cost`

---

## 2) 每个接口在做什么

### 2.1 通用市场/账户/交易接口说明
- `load_markets`: 拉取并缓存市场元数据（精度、最小下单量、合约参数、symbol 映射）。
- `load_time_difference`: 同步交易所时间差，降低时间戳类报错（例如 -1021）。
- `fetch_ticker`: 拉取单个交易对实时行情（last/bid/ask/volume 等）。
- `fetch_tickers`: 批量拉取多个交易对或全市场行情。
- `fetch_ohlcv`: 拉取 K 线数据（open/high/low/close/volume）。
- `fetch_funding_rate`: 拉取单个合约当前资金费率。
- `fetch_funding_rates`: 批量拉取多个合约当前资金费率。
- `fetch_funding_history`: 拉取资金费历史结算记录。
- `fetch_funding_rate_history`: 拉取资金费率历史时间序列。
- `fetch_balance`: 拉取账户余额（现货或合约账户）。
- `fetch_positions`: 拉取持仓列表（支持全量或按 symbol 过滤）。
- `fetch_position`: 拉取单个持仓（部分交易所支持）。
- `fetch_ledger`: 拉取账本流水（入金、费用、资金费等）。
- `fetch_trading_fee`: 拉取交易对费率（maker/taker）。
- `create_order`: 下单接口（市价/限价等）。
- `set_leverage`: 设置杠杆倍数。
- `set_margin_mode`: 设置保证金模式（cross/isolated）。
- `set_position_mode`: 设置持仓模式（单向/双向）。

### 2.2 私有原生接口说明（按交易所）
- `privateGetAccount` (Binance): 读取现货账户资产信息（你们用于规避受限 SAPI 路径）。
- `fapiPrivateGetIncome` (Binance): 读取合约收入流水（含资金费）。
- `fapiPrivateGetLeverageBracket` (Binance): 读取合约杠杆档位上限。
- `fapiPrivatePostMarginType` (Binance): 设置合约保证金模式。
- `fapiPrivate_post_positionside_dual` (Binance): 设置双向持仓模式。
- `privateGetAccountBills` (OKX): 读取 OKX 账户账单流水。
- `private_post_account_set_position_mode` (OKX): 设置 OKX 持仓模式。
- `privateGetV5AccountTransactionLog` (Bybit): 读取 Bybit V5 账户交易流水。
- `private_post_v5_position_switch_mode` (Bybit): 切换 Bybit 持仓模式。
- `privateFuturesGetSettleAccountBook` (Gate): 读取 Gate 合约账本/结算流水。
- `contractPrivateGetPositionFundingRecords` (MEXC): 读取 MEXC 合约资金费记录。

### 2.3 交易参数与精度辅助接口说明
- `market`: 从已加载 markets 中解析交易对元数据（本地解析）。
- `amount_to_precision`: 将下单数量格式化到交易所允许精度。
- `cost_to_precision`: 将下单金额格式化到交易所允许精度。
- `create_market_buy_order_with_cost`: 按“花费金额”下市价买单（常用于 Gate）。

---

## 3) 主要调用文件

核心调用集中在：
- `backend/core/exchange_manager/funding_data.py`
- `backend/core/exchange_manager/market_data.py`
- `backend/core/exchange_manager/leverage_margin.py`
- `backend/core/exchange_manager/order_close.py`
- `backend/core/exchange_manager/hedge_orders.py`
- `backend/core/exchange_manager/registry.py`

其次在：
- `backend/core/data_collector/funding_collect.py`
- `backend/core/data_collector/market_prices.py`
- `backend/core/funding_ledger/cursor.py`
- `backend/core/funding_ledger/sources.py`
- `backend/core/spread_arb_engine/*`
- `backend/core/spot_basis_*`


---

## 4) 重点说明

1. 主产品线未使用 `ccxt.pro` 的 `watch*` 接口作为主链路。
2. 主链路是 CCXT REST + 交易所私有 raw 接口混用。
3. 有一部分调用（`amount_to_precision`、`cost_to_precision`、`market`）是本地参数换算/精度处理，不是网络请求。


---

## 5) 提取方式（可复现）

```bash
rg -o "inst\.[A-Za-z_][A-Za-z0-9_]*\(" backend/core backend/domains backend/infra \
  | sed -E 's/.*inst\.([A-Za-z_][A-Za-z0-9_]*)\(.*/\1/' \
  | sort -u
```
