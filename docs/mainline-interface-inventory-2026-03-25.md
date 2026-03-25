# 主产品线接口盘点（2026-03-25）

## 1. 目的与范围

本文档用于回答：当前主产品线（`backend/`）到底在用哪些交易所接口。

范围说明：
- 仅统计主产品线代码（`backend/`）
- 不包含 `scripts/sandbox_ccxt_pro/` 的实验/压测脚本
- 重点聚焦交易所读写接口（行情、账户、仓位、下单、历史）

---

## 2. 结论摘要

当前主产品线是 **CCXT REST 主链路**，并非 CCXT Pro 主链路。

- 主调用入口在 `backend/core/exchange_manager/*`
- `backend/` 内未发现 `ccxt.pro` 或 `watch_*` 调用
- 仅有一个独立的 OKX 私有 WS 组件（非 ccxt.pro）

---

## 3. 主链路分层与入口

### 3.1 交易所能力层（核心）
- `backend/core/exchange_manager/__init__.py`
- `backend/core/exchange_manager/registry.py`
- `backend/core/exchange_manager/funding_data.py`
- `backend/core/exchange_manager/market_data.py`
- `backend/core/exchange_manager/leverage_margin.py`
- `backend/core/exchange_manager/order_close.py`

### 3.2 域与网关层（对外复用）
- `backend/infra/exchange/gateway.py`
- `backend/infra/market/gateway.py`
- `backend/core/data_collector/funding_collect.py`
- `backend/core/data_collector/market_prices.py`

### 3.3 运行时拉起
- `backend/main.py`
  - 启动调度任务（funding、价格、风控等）
  - 启动 OKX 私有 WS supervisor

---

## 4. 接口清单（主产品线正在使用）

## 4.1 行情与市场数据（REST）

统一/常用接口：
- `load_markets`
- `fetch_ticker`
- `fetch_tickers`
- `fetch_ohlcv`
- `fetch_funding_rates`
- `fetch_funding_rate`

主要落点：
- `backend/core/exchange_manager/funding_data.py`
- `backend/core/exchange_manager/foundations.py`
- `backend/core/data_collector/funding_collect.py`
- `backend/core/data_collector/market_prices.py`

用途：
- 资金费率拉取
- 标记价/最新价更新
- K 线回测/统计
- 24h 成交量缓存

## 4.2 账户与仓位（REST）

统一/常用接口：
- `fetch_balance`
- `fetch_positions`
- `fetch_ledger`

主要落点：
- `backend/core/exchange_manager/market_data.py`
- `backend/core/exchange_manager/order_close.py`
- `backend/core/exchange_manager/foundations.py`
- `backend/core/spread_arb_engine/*`
- `backend/domains/dashboard/router_accounts.py`

用途：
- 账户权益估值
- 仓位读取/校验
- 对账与风控

## 4.3 交易与杠杆（REST/私有）

统一/常用接口：
- `create_order`
- `set_leverage`
- `set_margin_mode`
- `set_position_mode`

主要落点：
- `backend/core/exchange_manager/funding_data.py`
- `backend/core/exchange_manager/leverage_margin.py`
- `backend/core/exchange_manager/order_close.py`
- `backend/core/exchange_manager/hedge_orders.py`

用途：
- 开平仓
- 杠杆设置
- 对冲模式（双向持仓/仓位模式）

## 4.4 交易所私有原生接口（按交易所分支）

Binance：
- `privateGetAccount`
- `fapiPrivateGetIncome`
- `fapiPrivateGetLeverageBracket`
- `fapiPrivatePostMarginType`

OKX：
- `privateGetAccountBills`
- `private_post_account_set_position_mode`

Bybit：
- `privateGetV5AccountTransactionLog`
- `private_post_v5_position_switch_mode`

主要落点：
- `backend/core/exchange_manager/market_data.py`
- `backend/core/exchange_manager/funding_data.py`
- `backend/core/exchange_manager/leverage_margin.py`
- `backend/core/exchange_manager/order_close.py`

---

## 5. WebSocket 使用现状

### 5.1 主链路（采集/策略）
- 未使用 `ccxt.pro` `watch_*` 作为主产品线数据主链路
- 主链路核心仍是 REST 拉取 + 定时刷新

### 5.2 独立 WS 组件
- `backend/core/okx_private_ws.py`
- 使用 `websockets` 直连 OKX 私有 WS（account/positions/orders）
- 在 `backend/main.py` 启动和关闭：
  - `start_okx_private_ws_supervisor()`
  - `stop_okx_private_ws_supervisor()`

---

## 6. 代码定位速查

核心文件：
- `backend/core/exchange_manager/funding_data.py`
- `backend/core/exchange_manager/market_data.py`
- `backend/core/exchange_manager/order_close.py`
- `backend/core/exchange_manager/leverage_margin.py`
- `backend/core/exchange_manager/registry.py`
- `backend/core/data_collector/funding_collect.py`
- `backend/core/data_collector/market_prices.py`
- `backend/core/okx_private_ws.py`
- `backend/main.py`

网关暴露：
- `backend/infra/exchange/gateway.py`
- `backend/infra/market/gateway.py`

---

## 7. 与 sandbox ccxt_pro 的关系

- `scripts/sandbox_ccxt_pro/` 当前用于实验、压测、采集服务化验证
- 尚未替换 `backend/` 主产品线的交易所读写主链路
- 因此主产品线与 sandbox 当前是并行状态，不是“已迁移完成”状态

---

## 8. 一句话结论

主产品线当前是：
- **REST 主驱动（CCXT）**
- **少量交易所私有 API 补充**
- **单独 OKX 私有 WS 组件**
- **未落地 ccxt.pro 作为主链路**
