# 收益口径字典 + 归因优先级 + 验收用例（冻结版）

## 0. 文档目标

本文件用于冻结收益分析的统一口径，作为以下模块的唯一真源：

- 收益分析看板（Analytics）
- 策略明细（Positions / Strategy Detail）
- 导出报表（CSV/API 导出）

冻结后禁止各页面自行计算，必须复用同一聚合结果。

版本：`v1.0`  
冻结日期：`2026-03-15`

---

## 1. 统一口径字典（必须一致）

### 1.1 统一公式

`Total PnL (USDT) = Spread PnL (USDT) + Funding PnL (USDT) - Fee (USDT)`

说明：

- `slippage` 口径冻结为：`先采集但不并入 Total`（`slippage_policy=excluded_from_total`）。
- 若后续切换为并入口径，必须提升版本号，并完成双轨验证后再切流。
- 所有字段都按 `USDT` 折算后再聚合，不允许前端自行换算。

### 1.2 统一单位、方向、时间边界

- 计价币种：`USDT`
- 方向约定：  
  - `PnL > 0` 表示盈利  
  - `Funding PnL > 0` 表示收到资金费，`< 0` 表示支付资金费  
  - `Fee` 是成本字段，存储为正数，在公式中统一减去
- 统计时间边界：`UTC+8`（查询按北京时间日切）
- 存储时间：数据库继续使用 `UTC` 时间戳；查询层负责 `UTC+8` 切窗

### 1.3 字段定义（看板/明细/导出一致）

- `spread_pnl_usdt`：价差收益（已实现 + 未实现）
- `funding_pnl_usdt`：资金费收益（仅来自资金费流水归因结果）
- `fee_usdt`：交易手续费（统一费率来源 + 实际成交额）
- `total_pnl_usdt`：按统一公式计算结果
- `total_pnl_pct`：`total_pnl_usdt / capital_base_usdt`
- `capital_base_usdt`：策略初始保证金或约定本金基准（在 API 明确返回）

---

## 2. 资金费覆盖率口径（含分母）

覆盖率不能只看“抓到多少条”，必须有“应抓条数”。

### 2.1 事件分母：`expected_funding_event_count`

按每条策略腿（leg）计算“理论应发生资金费结算事件数”：

1. 先生成该交易所该合约的结算时刻序列（按交易所实际结算频率）。
2. 在策略腿持仓时间窗内，筛出结算时刻。
3. 若结算时刻对应的净持仓绝对值低于阈值（默认 `1e-8`），该事件不计入分母。

最终分母是所有腿之和。

### 2.2 事件分子：`captured_funding_event_count`

满足以下条件的资金费流水计入分子：

- 已通过幂等去重落库；
- 能够归因到具体策略腿；
- 金额和时间字段有效（非空且可解析）。

### 2.3 覆盖率定义

`funding_coverage = captured_funding_event_count / expected_funding_event_count`

质量分级：

- `ok`：`coverage >= 0.98`
- `partial`：`0 < coverage < 0.98`
- `missing`：`expected > 0` 且 `captured = 0`
- `na`：`expected = 0`

当 `missing` 时，前端必须显示 `missing` 状态，不允许静默显示 `0`。

---

## 3. 资金费归因规则（确定性优先级）

目标：同一条资金费流水在任何重跑场景下，归因结果完全一致。

### 3.1 候选策略集

对一条资金费流水 `E`（exchange/account/symbol/funding_time/side/amount）：

1. 先按 `exchange + account + symbol` 精确匹配策略腿；
2. 仅保留在 `funding_time` 时刻存在有效持仓的策略腿；
3. 方向不兼容的候选剔除（多/空与事件方向不匹配）。

### 3.2 冲突归因优先级（从高到低）

1. 持仓时间覆盖优先：`funding_time` 落在该策略腿有效持仓窗口内。
2. 仓位权重优先：按 `funding_time` 时刻绝对名义仓位占比分摊。
3. 策略时间优先：若仍并列，优先 `created_at` 更早者。
4. 稳定 Tie-break：若仍并列，选 `strategy_id` 更小者。

备注：第 2 条允许“按仓位比例拆分归因”，防止重叠换仓时错误全额归一条策略。

### 3.3 特殊场景处理

- 部分成交：按已成交仓位进入归因，不用下单目标仓位。
- 反向开平（同窗翻向）：按结算时刻的净仓位方向归因；净仓位为 0 则该事件不应计入分母。
- 跨账户对冲：禁止跨账户归因，资金费只在同账户内匹配。
- 未匹配事件：落入 `unassigned_funding`，并进入对账告警。

---

## 4. 缺失与展示规则

- `funding_quality = missing` 时：
  - `funding_pnl_usdt` 返回 `null`（不是 `0`）
  - `total_pnl_usdt` 返回 `null` 或 `partial` 标记（由 API `quality` 字段指示）
  - UI 显示“资金费缺失（missing）”，并提供覆盖率与最后错误信息

- 仅当 `funding_quality in {ok, partial, na}` 时允许展示数值。

---

## 5. 验收用例（最小集合）

### 5.1 一致性验收

- 日级校验：`Σ策略明细 total_pnl_usdt` 与 `看板 total_pnl_usdt` 误差  
  `<= max(5 USDT, 0.1%)`
- 策略级校验：策略明细与导出中同策略同时间窗数值完全一致

### 5.2 资金费完整性验收

- `captured_funding_event_count <= expected_funding_event_count`
- `coverage` 可回溯到明细事件列表
- `missing` 策略在 UI 可见且可筛选

### 5.3 确定性验收

同一时间窗重跑三次，以下字段必须完全一致：

- `funding_pnl_usdt`
- `funding_coverage`
- `funding_quality`
- `unassigned_funding_count`

### 5.4 边界验收（UTC+8）

覆盖以下时间点：

- `00:00:00` 日切
- 月末跨月
- 夏令时无关（统一按 UTC+8 统计，不随本地时区变化）

### 5.5 场景用例表

- `CASE-01`：单策略单腿正常结算，期望 `coverage=1.0` 且全额归因
- `CASE-02`：同 symbol 同账户两策略重叠，期望按仓位比例拆分
- `CASE-03`：换仓窗口内旧策略平仓新策略开仓，期望按结算时刻净仓位归因
- `CASE-04`：资金费 API 无返回，期望 `funding_quality=missing` 且 UI 不显示 0
- `CASE-05`：跨账户同 symbol，期望互不归因

---

## 6. 变更控制

任何口径变更必须：

1. 更新本文件版本号；
2. 提供迁移影响说明（看板/明细/导出/API）；
3. 在双轨期完成旧口径对照验证后再切流。
