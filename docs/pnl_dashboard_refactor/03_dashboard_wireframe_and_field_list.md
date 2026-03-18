# 页面线框与字段清单（收益分析看板 + 策略明细）

## 0. 设计目标

1. 先展示“机会与风险”，再展示细节。  
2. 每个关键数字都能回答三个问题：  
   - 这是什么（名词解释）  
   - 从哪里来（数据来源）  
   - 是否可信（质量状态）
3. `missing` 必须显式可见，不能伪装成 0。

---

## 1. 页面结构（桌面端）

建议采用从上到下 6 区块：

1. 全局状态条  
2. 收益趋势图  
3. KPI 卡片  
4. 策略状态概览  
5. 盈利/亏损归因  
6. 策略明细表 + 抽屉详情

### 1.1 线框（ASCII）

```text
[数据时间][UTC+8][资金费覆盖率][对账状态][异常策略数]

[净收益柱状 + 累计收益曲线]   [7/30/90/180/全部] [日/周/月]

[净收益][盈利][亏损][收益率][手续费][资金费]

[启动策略][结束策略][延续策略]

[盈利归因(按类型->策略)]   [亏损归因(按类型->策略)]

[策略明细表(可筛选/排序/导出)] -> [策略详情抽屉]
```

---

## 2. 字段清单与展示规则

## 2.1 全局状态条（新增）

- `as_of`：数据截止时间
- `timezone`：固定显示 `UTC+8`
- `funding_coverage`：如 `96.4%`
- `funding_quality`：`ok/partial/missing/na`
- `reconcile_status`：`pass/warn/fail`
- `anomaly_strategy_count`

展示规则：

- `missing` 或 `fail` 用红色状态点
- 支持点击查看“最后错误”和“未归因事件数”

## 2.2 趋势图

- 主图：`daily_total_pnl_usdt` 柱状
- 副图：`cumulative_total_pnl_usdt` 线
- 可选叠加：`daily_funding_pnl_usdt`

交互：

- 时间范围：`7/30/90/180/all`
- 粒度：`day/week/month`
- Tooltip 显示：`spread/funding/fee/total/quality`

## 2.3 KPI 卡片

卡片字段统一来自 `GET /api/pnl/v2/summary`：

- `total_pnl_usdt`
- `total_profit_usdt`
- `total_loss_usdt`
- `pnl_pct`
- `total_fee_usdt`
- `total_funding_pnl_usdt`

每张卡片底部都显示：

- `source`（聚合快照 / 实时补算）
- `as_of`
- `quality`

## 2.4 策略状态概览

- `started_count`
- `closed_count`
- `continued_count`

可点击进入对应筛选后的策略列表。

## 2.5 盈亏归因区

左右两栏：

- 左：盈利归因（按类型汇总，可展开到策略）
- 右：亏损归因（按类型汇总，可展开到策略）

类型建议：

- `费率套利`
- `跨所套利`
- `基差交易`

每个分组字段：

- `strategy_count`
- `pnl_usdt`
- `pnl_ratio`

## 2.6 策略明细表

核心列：

- `strategy_id`
- `symbol`
- `long_exchange` / `short_exchange`
- `spread_pnl_usdt`
- `funding_pnl_usdt`（可空）
- `fee_usdt`
- `total_pnl_usdt`（可空）
- `total_pnl_pct`
- `funding_coverage`
- `funding_quality`
- `status`
- `created_at` / `closed_at`

规则：

- `funding_quality=missing` 时，`funding_pnl_usdt` 显示 `missing` 标签，不显示 `0`
- `total_pnl_usdt` 若受 missing 影响，显示 `--` + `partial` 标签

---

## 3. 策略详情抽屉（重点改造）

抽屉分 4 块：

1. 基本信息
2. 组分盈亏
3. Legs 明细
4. 资金费事件明细

## 3.1 组分盈亏块

- `Spread PnL`
- `Funding PnL`
- `Fee`
- `Total PnL`

每项右侧展示：

- `quality`
- `source`
- `as_of`

## 3.2 Legs 明细块（修复 entry 可解释性）

每条腿增加双值：

- `entry_local`（本地记录）
- `entry_exchange`（交易所回读）

当两者偏差超过阈值（默认 `0.05%`）：

- 行内黄色告警
- Hover 显示“偏差值 + 最近同步时间”

## 3.3 资金费事件明细块

字段：

- `funding_time`
- `exchange`
- `symbol`
- `amount_usdt`
- `assigned_ratio`
- `source`
- `source_ref`
- `assignment_rule`

支持快速排错：一键筛 `unassigned`。

---

## 4. 名词角标字典（需要全部覆盖）

以下名词都应有 `i` 角标 Tooltip（你前面提到的需求）：

- `Spread PnL`
- `Funding PnL`
- `Fee`
- `Total PnL`
- `Funding Coverage`
- `Funding Quality`
- `Current Annualized`
- `Initial Margin`
- `Unrealized PnL`
- `Realized PnL`
- `延续策略`
- `归因`

Tooltip 内容规则：

- 不超过 2 行
- 解释 + 公式（如适用）
- 明确单位（USDT / %）

---

## 5. 移动端适配

- 顶部状态条折叠为两行
- KPI 卡片 `2 列 x 3 行`
- 趋势图保留，明细表改卡片列表
- 抽屉全屏展示，事件明细支持横向滚动

---

## 6. UI 验收标准

1. 任一数字点开后能看到来源与质量（可追溯）。  
2. `missing` 在看板和明细都可见，不出现“误导性 0”。  
3. 同一策略在看板、明细、导出三处数值一致。  
4. 名词角标覆盖率 100%。  
5. 桌面与移动端均可用，无关键信息丢失。
