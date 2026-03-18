# 记忆补充（2026-03-14）

## 本轮确认
- 暂不启动“持续采集落库”工作。
- E24 口径改为仅使用真实观测点（real observed buckets）计算。
- 15m 前向填充序列只用于展示连续性与诊断，不参与 E24 与置信度主计算。

## 技术落地
- 文件：backend/api/spot_basis.py
- 变更：_load_funding_stability 同时输出 obs/fill 两套统计，严格评分链路读取 obs 统计。
- 新增状态字段：stats_mode=obs_only_for_e24，便于前端和审计识别当前口径。

# 记忆补充（2026-03-15）

## 本轮确认
- 不再推进“3天15分钟费率快照后台全量补齐”方向（API 无法稳定拿到真实 15m 快照，继续做意义不大）。
- 继续保留并强化自动对账；盈亏页资产口径按“现货+合约全币种折算 USDT”。

## 技术落地
- 自动策略页移除历史补全相关 UI 与触发链路：
  - 去掉“历史补全进行中”卡片、相关轮询与自动启动逻辑。
  - 自动轮次不再触发 funding history refresh gate。
- 自动状态接口收口：
  - `/api/spot-basis/auto-status` 不再返回 `history_refresh_*` 字段。
  - 前端 `services/api.js` 移除未使用的历史补全 start/progress 导出。
- 盈亏资产口径更新：
  - `backend/api/analytics.py` 的总资产读取优先新鲜 `EquitySnapshot`（120s），过期回退实时抓取。
  - 返回 `total_account_meta`，标注 `valuation_scope=spot+swap_all_tokens_mark_to_usdt` 与来源（自动快照/实时抓取）。
  - 前端 Analytics 文案同步为“现货+合约全币种折算”。
- 恢复单入场价修复（重点）：
  - `backend/core/spot_basis_reconciler.py` 增强恢复策略入场价同步逻辑，兼容两种恢复原因：
    - `recovered_untracked_open_from_exchange`
    - `recovered_untracked_open_from_exchange_auto`
  - spot 腿入场价同步锚点：优先交易所实时 perp entry，拿不到则回退 perp 腿数据库 entry。
  - 已对本地库策略 `#292` 执行一次修正，当前两腿 entry 已对齐为 `0.015749`。
- 自动策略控制页术语角标：
  - `frontend/src/pages/SpotBasisAuto/index.jsx` 为开关项、分组标题、参数名统一加 Tooltip 解释，便于对外讨论。

# 记忆补充（2026-03-16）

## 本轮确认
- 收益分析看板默认视角切到 `active`，避免历史 `closed/error` 的资金费缺失污染主看板判断。
- 保留 `all` 视角用于审计与排查，且 summary/list/export 必须同口径同过滤条件。

## 技术落地
- Spread PnL 口径修复（核心）：
  - `backend/api/pnl_v2.py` 与 `backend/api/analytics.py` 的 `_calc_spread_pnl` 已纳入 `repair_reduce` 现金流。
  - 修复后 `Strategy #294` 的 spread 从错误的约 `-5.231368` 回到约 `-0.424552`。
  - 新增回归测试：`test_spread_includes_repair_reduce_cashflow`。
- Strategy Detail 500 修复：
  - `backend/api/pnl_v2.py` 补充 `utc_now` 导入，修复 `_fetch_exchange_entry_for_position` 命中 entry 时 `NameError`。
  - 该函数增加容错：兼容非 list 的交易所返回、跳过 malformed item，防止明细抽屉偶发 500。
  - 新增回归测试：
    - `test_fetch_exchange_entry_handles_non_list_payload`
    - `test_fetch_exchange_entry_skips_malformed_items`
- Analytics 页口径统一改造：
  - `frontend/src/pages/Analytics/index.jsx` 新增 `scope`（默认 `active`，可切 `all`）。
  - summary/list/export 全部使用同一 `status` 参数。
  - 顶部状态条增加 `scope` 展示，便于解释当前统计口径。
  - `frontend/src/services/api.js` 的 `getPnlV2Summary` 支持对象参数（含 `status`）。

## 脏数据清理
- 新增脚本：`backend/tools/cleanup_dirty_strategies.py`（默认 dry-run，可 `--apply`）。
- 清理规则：
  - `status=error`
  - 无 `trade_logs`
  - 无 `funding_assignments`
- 已执行 `--apply`，结果：
  - 删除策略 `132`
  - 删除关联仓位 `264`
  - 删除交易日志 `0`
  - 删除资金费归因 `0`
- 清理后复查：`dirty_strategy_candidates=0`。

## 验证结果
- `python -m unittest backend.tests.test_pnl_v2_minimum -v` 通过（27/27）。
- `npm.cmd run build` 通过（仅既有 `@antv` sourcemap warnings，无新增构建错误）。
