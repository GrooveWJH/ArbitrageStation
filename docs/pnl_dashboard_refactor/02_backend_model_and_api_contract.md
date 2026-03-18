# 后端模型与 API 契约（收益看板重构）

## 0. 目标

把“实时临时计算”改成“流水落库 + 统一聚合 + 可追溯质量标记”，解决：

- 资金费抓取不稳定导致的误差
- 看板、策略明细、导出口径不一致
- 缺失数据被静默显示为 0

---

## 1. 数据模型（新增/调整）

## 1.1 资金费流水表 `funding_fee_ledger`

用途：统一接收交易所资金费记录，先去重落库，再做归因与聚合。

建议字段：

- `id` bigint pk
- `exchange_id` int not null
- `account_key` varchar(128) not null  
  现阶段可先使用 `exchange_id` 字符串化；后续可扩展到同交易所多账户
- `symbol` varchar(64) not null
- `side` varchar(16) null
- `funding_time` datetime not null (UTC)
- `amount_usdt` decimal(28, 12) not null
- `source` varchar(32) not null  
  值示例：`binance_income`, `okx_bills`, `bybit_transaction`, `gate_custom`, `mexc_custom`, `ccxt_ledger_fallback`
- `source_ref` varchar(255) null  
  交易所原始流水主键；不可用时按降级规则生成
- `raw_payload` text null
- `ingested_at` datetime not null
- `normalized_hash` varchar(64) not null

强幂等唯一键（逻辑）：

`exchange_id + account_key + symbol + funding_time + side + amount_usdt`

说明：

- `source` 与 `source_ref` 都仅用于追踪来源，不参与主幂等键，避免适配器切换导致重复入账。

时区约束：

- `funding_time` 底层统一存 `UTC`；
- 展示层统一转 `UTC+8`；
- 日级归因/统计窗口按 `UTC+8` 日切计算，但不改写底层时间戳。

数据库唯一约束（物理）建议两层：

1. `uniq_funding_primary(normalized_hash)`  
2. `uniq_funding_fallback(exchange_id, account_key, symbol, funding_time, side, amount_usdt, source)`

`source_ref` 缺失时的降级规则：

1. 优先取交易所返回流水 id（如 `billId` / `txId` / `id`）
2. 次选 `orderId + funding_time`
3. 最后使用标准化 payload 的哈希（稳定字段拼接）

## 1.2 资金费归因表 `funding_fee_assignment`

用途：把 `funding_fee_ledger` 精确归因到策略与策略腿，支持拆分归因。

字段建议：

- `ledger_id` bigint not null
- `strategy_id` int not null
- `position_id` int null
- `assigned_amount_usdt` decimal(28, 12) not null
- `assigned_ratio` decimal(10, 8) not null
- `rule_version` varchar(16) not null (`v1`)
- `assigned_at` datetime not null

唯一约束：

- `uniq_assignment(ledger_id, strategy_id, position_id)`

## 1.3 抓取游标表 `funding_fetch_cursor`

用途：支持增量抓取、失败重试、断点续跑。

字段建议：

- `exchange_id`
- `account_key`
- `symbol`（可空；按交易所能力决定）
- `cursor_type`（`time_ms` / `page_token` / `bill_id`）
- `cursor_value`
- `last_success_at`
- `last_error`
- `retry_count`

唯一约束：

- `uniq_cursor(exchange_id, account_key, symbol, cursor_type)`

## 1.4 统一聚合快照表 `strategy_pnl_snapshot`（可选但推荐）

用途：避免每次页面请求全量重算，提供统一读模型。

核心字段：

- `strategy_id`
- `as_of`（UTC）
- `spread_pnl_usdt`
- `funding_pnl_usdt`（可空）
- `fee_usdt`
- `total_pnl_usdt`（可空）
- `funding_expected_event_count`
- `funding_captured_event_count`
- `funding_coverage`
- `funding_quality`（`ok/partial/missing/na`）
- `quality`（整体质量）

---

## 2. 聚合与任务流程

## 2.1 处理链路

1. 抓取器按交易所适配器拉取资金费流水
2. 标准化 + 强幂等落库 `funding_fee_ledger`
3. 归因引擎按冻结规则写入 `funding_fee_assignment`
4. 聚合器更新 `strategy_pnl_snapshot`
5. API 仅从统一聚合结果读取

## 2.2 定时任务建议

- `funding_ingest_job`：每 3-5 分钟
- `funding_attribution_job`：每 3-5 分钟（可与 ingest 串联）
- `funding_backfill_job`：低优先级补抓（历史窗口）
- `daily_reconcile_job`：每日 `UTC+8 00:10`

## 2.3 交易所适配优先级

第一批必须专项实现：

- `gate`
- `mexc`

保留 `ccxt_ledger_fallback`，但仅作为兜底，且必须打低质量标记。

---

## 3. API 契约（v2）

约定：看板、策略明细、导出全部复用同一套 v2 聚合接口。

## 3.1 `GET /api/pnl/v2/summary`

返回示例字段：

- `as_of`
- `timezone`（固定 `UTC+8`）
- `total_spread_pnl_usdt`
- `total_funding_pnl_usdt`（可空）
- `total_fee_usdt`
- `total_pnl_usdt`（可空）
- `funding_expected_event_count`
- `funding_captured_event_count`
- `funding_coverage`
- `funding_quality`
- `quality`
- `warnings[]`

## 3.2 `GET /api/pnl/v2/strategies`

查询参数：

- `status`
- `start_date` / `end_date`（UTC+8 日边界）
- `quality`
- `page` / `page_size`

每行字段：

- `strategy_id`
- `symbol`
- `spread_pnl_usdt`
- `funding_pnl_usdt`（可空）
- `fee_usdt`
- `total_pnl_usdt`（可空）
- `funding_expected_event_count`
- `funding_captured_event_count`
- `funding_coverage`
- `funding_quality`
- `quality`
- `as_of`

## 3.3 `GET /api/pnl/v2/strategies/{id}`

返回：

- 策略总览（统一口径字段）
- 资金费事件明细（ledger + assignment）
- 质量信息（missing 原因、最后错误、覆盖率）

## 3.4 `GET /api/pnl/v2/export`

导出字段与 `strategies` 完全同构，禁止另算。

---

## 4. 缺失语义（后端必须保证）

- 当 `funding_quality = missing`：
  - `funding_pnl_usdt = null`
  - `total_pnl_usdt = null` 或 `quality=partial`（由产品 UI 决定展示方式）
- API 同时返回 `quality_reason`，例如：
  - `funding_api_no_data`
  - `cursor_gap_detected`
  - `assignment_conflict`

---

## 5. 双轨校验上线策略

## 5.1 双轨期

- 时长：`1-2 周`
- 新旧口径并行计算，不切流
- 每日自动输出对比报告

## 5.2 日级验收阈值

- `abs(new_total - old_total) <= max(5 USDT, 0.1%)`
- `Σ策略 total_pnl_usdt` 与 `summary total_pnl_usdt` 一致
- `missing` 比例低于告警阈值（建议 `< 2%`）

## 5.3 切流条件

满足连续 5 个交易日阈值内后，才允许把前端默认源切到 v2。

---

## 6. 实施节奏（修正后）

- Phase A（口径冻结 + API 草约 + 数据模型迁移）：`1-2 天`
- Phase B（资金费流水化 + gate/mexc 适配 + 对账）：`5-7 天`
- Phase C（前端切 v2 + 双轨观测 + 切流）：`3-5 天`

总计建议：`9-14 天`（含双轨观测时间，不含额外交易所扩展）。
