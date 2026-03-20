import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  Badge,
  Button,
  Card,
  Col,
  Empty,
  Input,
  InputNumber,
  Popconfirm,
  Row,
  Segmented,
  Select,
  Space,
  Spin,
  Statistic,
  Switch,
  Table,
  Tag,
  Tooltip,
  Typography,
  message,
} from 'antd';
import {
  QuestionCircleOutlined,
  ReloadOutlined,
  RobotOutlined,
  SaveOutlined,
  SearchOutlined,
} from '@ant-design/icons';
import {
  getSpotBasisAutoConfig,
  getSpotBasisAutoStatus,
  getSpotBasisHistory,
  resetSpotBasisDrawdownWatermark,
  runSpotBasisAutoCycleOnce,
  setSpotBasisAutoStatus,
  updateSpotBasisAutoConfig,
} from '../../services/endpoints/spotBasisApi';
import {
  useSpotBasisAutoActiveExchangesQuery,
  useSpotBasisAutoDecisionPreviewQuery,
  useSpotBasisAutoCycleLastQuery,
  useSpotBasisAutoCycleLogsQuery,
  useSpotBasisAutoExchangeFundsQuery,
  useSpotBasisAutoOpportunitiesQuery,
  useSpotBasisDrawdownWatermarkQuery,
} from '../../services/queries/spotBasisAutoQueries';

const PAD = { left: 58, right: 64, top: 10, bottom: 34 };
const HISTORY_CACHE_TTL_MS = 60 * 1000;
const historyCache = new Map();

const num = (v, d = 0) => {
  const x = Number(v);
  return Number.isFinite(x) ? x : d;
};
const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
const pctText = (v, p = 4) => `${num(v, 0).toFixed(p)}%`;
const keyOf = (r) => `${r.symbol}|${r.perp_exchange_id}|${r.spot_exchange_id}`;
const fmtVol = (v) => (num(v) >= 1e6 ? `${(num(v) / 1e6).toFixed(2)}M` : `${num(v).toFixed(0)}`);
const fmtPrice = (v) => (num(v) > 1 ? `$${num(v).toFixed(4)}` : `$${num(v).toFixed(8)}`);
const fmtUsd = (v, p = 2) => `$${num(v, 0).toFixed(p)}`;
const fmtTime = (ms) => {
  if (!Number.isFinite(ms)) return '--';
  try {
    return new Date(ms).toLocaleString('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return '--';
  }
};

const fmtIsoTime = (iso) => {
  if (!iso) return '--';
  try {
    const dt = new Date(iso);
    if (Number.isNaN(dt.getTime())) return '--';
    return dt.toLocaleString('zh-CN', {
      month: '2-digit',
      day: '2-digit',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    });
  } catch {
    return '--';
  }
};

const errText = (e, fallback) =>
  e?.response?.data?.detail?.message ||
  e?.response?.data?.detail ||
  e?.response?.data?.message ||
  e?.response?.data?.error ||
  e?.response?.data ||
  e?.message ||
  fallback;

const fmtCountdown = (secs) => {
  const s = Math.max(0, Math.floor(num(secs, 0)));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  if (h > 0) return `${h}小时 ${String(m).padStart(2, '0')}分`;
  return `${String(m).padStart(2, '0')}分 ${String(sec).padStart(2, '0')}秒`;
};

const STRICT_HINT =
  '严格评分: 综合评分 = E24净期望 × 置信度 × 容量';

const CYCLE_STATUS_LABELS = {
  init: '初始化',
  disabled: '已停用',
  lock_held_by_other_worker: '执行锁被其他实例占用',
  throttled: '节流等待',
  retry_executed: '执行重试队列',
  hedge_repair_dry_run: '敞口修复(模拟)',
  hedge_repair_executed: '敞口修复(已执行)',
  hedge_repair_circuit_breaker: '敞口修复触发熔断',
  risk_reduce_no_action: '风控检查无动作',
  risk_reduce_dry_run: '风控降风险(模拟)',
  risk_reduce_executed: '风控降风险(已执行)',
  no_delta_to_rebalance: '无组合差额',
  rebalance_wait_confirm: '等待换仓确认轮次',
  rebalance_deadband_blocked: '换仓死区阻断',
  dry_run_plan: '调仓计划(模拟)',
  executed: '调仓已执行',
  error: '执行异常',
};

const CYCLE_MODE_META = {
  retry_only: { label: '仅重试轮次', color: 'magenta' },
  hedge_repair_only: { label: '仅敞口修复轮次', color: 'cyan' },
  risk_reduce_only: { label: '仅风控降仓轮次', color: 'orange' },
  portfolio_rebalance: { label: '组合再平衡轮次', color: 'blue' },
};

const cycleStatusColor = (status) => {
  const s = String(status || '');
  if (s === 'error' || s.includes('failed') || s.includes('circuit_breaker')) return 'error';
  if (s === 'executed' || s.includes('executed')) return 'success';
  if (s === 'throttled' || s.includes('blocked') || s.includes('wait')) return 'warning';
  if (s === 'disabled') return 'default';
  return 'processing';
};

const cycleStatusLabel = (status) => {
  const key = String(status || '');
  if (!key) return '--';
  return CYCLE_STATUS_LABELS[key] || '未知状态';
};

const cycleModeLabel = (mode) => {
  const key = String(mode || '');
  if (!key) return '--';
  return CYCLE_MODE_META[key]?.label || '未知轮次';
};

const cycleModeTag = (mode) => {
  const key = String(mode || '');
  if (!key) return <Tag>未标注轮次</Tag>;
  const meta = CYCLE_MODE_META[key];
  if (!meta) return <Tag title={key}>未知轮次</Tag>;
  return <Tag color={meta.color}>{meta.label}</Tag>;
};

const cycleSummaryText = (item) => {
  const parts = [];
  parts.push(`轮次 ${cycleModeLabel(item?.mode)}`);
  parts.push(`计划开/平 ${num(item?.open_plan_pairs, 0)}/${num(item?.close_plan_pairs, 0)}`);
  parts.push(`执行开/平 ${num(item?.opened_pairs, 0)}/${num(item?.closed_pairs, 0)}`);
  const retryPending = num(item?.retry_queue?.pending, 0);
  if (retryPending > 0) parts.push(`重试待处理 ${retryPending}`);
  if (item?.error) parts.push(`错误 ${String(item.error)}`);
  return parts.join(' | ');
};

const shortRowId = (rowId) => {
  const [symbol, perp, spot] = String(rowId || '').split('|');
  if (!symbol) return '--';
  return `${symbol} ${perp || '-'}->${spot || '-'}`;
};

const DEFAULT_CFG = {
  is_enabled: false,
  dry_run: true,
  refresh_interval_secs: 10,
  enter_score_threshold: 15,
  max_open_pairs: 5,
  target_utilization_pct: 60,
  min_pair_notional_usd: 300,
  max_pair_notional_usd: 3000,
  switch_min_advantage: 5,
  switch_confirm_rounds: 3,
  entry_conf_min: 0.55,
  hold_conf_min: 0.45,
  max_total_utilization_pct: 100,
  reserve_floor_pct: 2,
  fee_buffer_pct: 0.5,
  slippage_buffer_pct: 0.5,
  margin_buffer_pct: 1.0,
  min_capacity_pct: 12,
  max_impact_pct: 0.3,
  rebalance_min_relative_adv_pct: 5,
  rebalance_min_absolute_adv_usd_day: 0.5,
  data_stale_threshold_seconds: 20,
  api_fail_circuit_count: 5,
  execution_retry_max_rounds: 2,
  execution_retry_backoff_secs: 8,
  delta_epsilon_abs_usd: 5,
  delta_epsilon_nav_pct: 0.01,
  repair_timeout_secs: 20,
  repair_retry_rounds: 2,
  circuit_breaker_on_repair_fail: true,
  basis_shock_exit_z: 4,
  portfolio_dd_soft_pct: -2,
  portfolio_dd_hard_pct: -4,
};

const AUTO_TERM_HELP = {
  auto_control: '自动执行总控面板，负责候选扫描、开平仓调度与风控联动。',
  is_enabled: '总开关。开启后按扫描间隔持续运行自动决策；关闭后仅保留手动操作。',
  dry_run: '模拟模式只生成计划与日志，不下真实订单。',
  circuit_breaker_on_repair_fail: '敞口修复连续失败时触发熔断，暂停自动执行，避免风险扩大。',
  contract_entry_execution: '合约腿的默认下单模式与杠杆设置。',
  cross_margin_mode: '使用全仓保证金，共享账户保证金，减少单仓爆仓概率。',
  fixed_leverage_2x: '默认按 2 倍杠杆计算名义与保证金需求。',
  safety_cushion: '开仓前预留的风险缓冲资金，不参与可用名义分配。',
  unhedged_tolerance: '允许的净敞口偏差上限，超过即触发修复逻辑。',
  '执行与重试': '控制调度频率、执行失败后的重试次数与重试间隔。',
  '信号与准入': '控制入场评分、换仓门槛与置信度过滤。',
  '资金与组合': '控制总占用、目标占用、组合规模、单对最小名义与单对最大名义。',
  '动态安全垫': '按成本与保证金动态预留安全垫，防止高波动时过度开仓。',
  '成交与容量': '限制流动性不足和冲击成本过高的标的。',
  '换仓门槛': '控制换仓必须达到的相对与绝对收益增量。',
  '无敞口修复': '控制净敞口容忍区间和修复确认参数。',
  '数据与风控': '控制数据新鲜度、接口熔断和组合回撤防线。',
  refresh_interval_secs: '每轮自动扫描与执行调度的时间间隔。',
  execution_retry_max_rounds: '同一执行任务允许重试的最大轮数。',
  execution_retry_backoff_secs: '重试前等待时间，避免连续撞单或瞬时故障重试。',
  enter_score_threshold: '严格评分最低要求，低于该值不允许新开仓。',
  switch_min_advantage: '换仓候选相对当前持仓需要至少超出的收益比例。',
  switch_confirm_rounds: '换仓条件需连续满足的轮数，降低抖动换仓。',
  entry_conf_min: '开仓所需的最低置信度。',
  hold_conf_min: '持仓继续保留所需的最低置信度。',
  max_total_utilization_pct: '总资金利用率硬上限，超过后禁止新增仓位。',
  target_utilization_pct: '常态目标资金利用率，用于自动分配开仓预算。',
  max_open_pairs: '允许同时持有的最大币对数量。',
  min_pair_notional_usd: '单个币对允许开仓的最小名义价值。',
  max_pair_notional_usd: '单个币对允许开仓的最大名义价值（开仓单腿口径）。',
  reserve_floor_pct: '安全垫最小保底比例。',
  fee_buffer_pct: '为手续费预留的缓冲比例。',
  slippage_buffer_pct: '为成交滑点预留的缓冲比例。',
  margin_buffer_pct: '为保证金波动预留的缓冲比例。',
  min_capacity_pct: '候选容量低于该比例时不参与自动开仓。',
  max_impact_pct: '预估冲击成本高于该比例时禁止开仓。',
  rebalance_min_relative_adv_pct: '换仓所需的最小相对收益增益。',
  rebalance_min_absolute_adv_usd_day: '换仓所需的最小绝对收益增益（按天）。',
  delta_epsilon_abs_usd: '净敞口允许的绝对偏差阈值（USDT）。',
  delta_epsilon_nav_pct: '净敞口允许的 NAV 相对偏差阈值。',
  repair_timeout_secs: '单轮敞口修复的超时时间。',
  repair_retry_rounds: '敞口修复后连续确认达标的轮数。',
  data_stale_threshold_seconds: '行情/账户数据超过该时长视为陈旧数据。',
  api_fail_circuit_count: '连续 API 失败次数达到后触发风控熔断。',
  basis_shock_exit_z: '基差偏离历史均值的 Z 值超过阈值时触发退出保护。',
  portfolio_dd_soft_pct: '组合触发软回撤后的温和降风险阈值。',
  portfolio_dd_hard_pct: '组合触发硬回撤后的强制降风险阈值。',
  drawdown_watermark: '回撤计算使用的高水位。重置后会以当前 NAV 作为新的风险起点。',
  drawdown_reset_button: '将组合回撤高水位重置为当前 NAV，用于解除历史峰值导致的硬回撤阻断。',
};

const termLabel = (label, help) => (
  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, whiteSpace: 'nowrap' }}>
    <span>{label}</span>
    <Tooltip title={help || `${label}说明`} placement="top">
      <QuestionCircleOutlined style={{ color: '#8c8c8c', fontSize: 12 }} />
    </Tooltip>
  </span>
);

const CFG_FIELD_META = {
  refresh_interval_secs: { label: '扫描间隔', addonAfter: '秒', min: 3, max: 300, step: 1, int: true },
  execution_retry_max_rounds: { label: '执行重试轮数', min: 0, max: 20, step: 1, int: true },
  execution_retry_backoff_secs: { label: '重试退避', addonAfter: '秒', min: 1, max: 600, step: 1, int: true },
  enter_score_threshold: { label: '入场评分阈值', min: 0, max: 100, step: 0.1 },
  switch_min_advantage: { label: '换仓最小优势', addonAfter: '%', min: 0, max: 200, step: 0.1 },
  switch_confirm_rounds: { label: '换仓确认轮数', min: 1, max: 20, step: 1, int: true },
  entry_conf_min: { label: '入场置信度下限', min: 0, max: 1, step: 0.01 },
  hold_conf_min: { label: '持仓置信度下限', min: 0, max: 1, step: 0.01 },
  max_total_utilization_pct: { label: '总资金利用率上限', addonAfter: '%', min: 1, max: 100, step: 0.5 },
  target_utilization_pct: { label: '目标资金利用率', addonAfter: '%', min: 1, max: 100, step: 0.5 },
  reserve_floor_pct: { label: '安全垫下限', addonAfter: '%', min: 0, max: 30, step: 0.1 },
  fee_buffer_pct: { label: '手续费缓冲', addonAfter: '%', min: 0, max: 30, step: 0.1 },
  slippage_buffer_pct: { label: '滑点缓冲', addonAfter: '%', min: 0, max: 30, step: 0.1 },
  margin_buffer_pct: { label: '保证金缓冲', addonAfter: '%', min: 0, max: 30, step: 0.1 },
  max_open_pairs: { label: '最大持仓币对数', min: 1, max: 100, step: 1, int: true },
  min_pair_notional_usd: { label: '单对最小名义', addonAfter: 'USD', min: 1, max: 1000000, step: 1 },
  max_pair_notional_usd: { label: '单对最大名义', addonAfter: 'USD', min: 1, max: 1000000, step: 1 },
  min_capacity_pct: { label: '容量下限', addonAfter: '%', min: 0, max: 100, step: 0.1 },
  max_impact_pct: { label: '冲击成本上限', addonAfter: '%', min: 0.01, max: 100, step: 0.01 },
  rebalance_min_relative_adv_pct: { label: '换仓相对增益门槛', addonAfter: '%', min: 0, max: 200, step: 0.1 },
  rebalance_min_absolute_adv_usd_day: { label: '换仓绝对增益门槛', addonAfter: 'USD/天', min: 0, max: 100000, step: 0.1 },
  delta_epsilon_abs_usd: { label: '敞口容忍(绝对)', addonAfter: 'USD', min: 0, max: 100000, step: 0.5 },
  delta_epsilon_nav_pct: { label: '敞口容忍(NAV)', addonAfter: '%', min: 0, max: 100, step: 0.001 },
  repair_timeout_secs: { label: '敞口修复超时', addonAfter: '秒', min: 1, max: 3600, step: 1, int: true },
  repair_retry_rounds: { label: '敞口修复确认轮数', min: 1, max: 20, step: 1, int: true },
  data_stale_threshold_seconds: { label: '数据陈旧阈值', addonAfter: '秒', min: 0, max: 3600, step: 1, int: true },
  api_fail_circuit_count: { label: '接口熔断计数', min: 1, max: 200, step: 1, int: true },
  basis_shock_exit_z: { label: '基差冲击退出Z', min: 0, max: 20, step: 0.1 },
  portfolio_dd_soft_pct: { label: '组合软回撤阈值', addonAfter: '%', min: -100, max: 0, step: 0.1 },
  portfolio_dd_hard_pct: { label: '组合硬回撤阈值', addonAfter: '%', min: -100, max: 0, step: 0.1 },
};

const CFG_SECTIONS = [
  { title: '执行与重试', keys: ['refresh_interval_secs', 'execution_retry_max_rounds', 'execution_retry_backoff_secs'] },
  { title: '信号与准入', keys: ['enter_score_threshold', 'switch_min_advantage', 'switch_confirm_rounds', 'entry_conf_min', 'hold_conf_min'] },
  { title: '资金与组合', keys: ['max_total_utilization_pct', 'target_utilization_pct', 'max_open_pairs', 'min_pair_notional_usd', 'max_pair_notional_usd'] },
  { title: '动态安全垫', keys: ['reserve_floor_pct', 'fee_buffer_pct', 'slippage_buffer_pct', 'margin_buffer_pct'] },
  { title: '成交与容量', keys: ['min_capacity_pct', 'max_impact_pct'] },
  { title: '换仓门槛', keys: ['rebalance_min_relative_adv_pct', 'rebalance_min_absolute_adv_usd_day'] },
  { title: '无敞口修复', keys: ['delta_epsilon_abs_usd', 'delta_epsilon_nav_pct', 'repair_timeout_secs', 'repair_retry_rounds'] },
  { title: '数据与风控', keys: ['data_stale_threshold_seconds', 'api_fail_circuit_count', 'basis_shock_exit_z', 'portfolio_dd_soft_pct', 'portfolio_dd_hard_pct'] },
];

const makeTicks = (min, max, count = 5) => {
  if (!Number.isFinite(min) || !Number.isFinite(max)) return [0];
  if (Math.abs(max - min) < 1e-12) return [min];
  const out = [];
  for (let i = 0; i < count; i += 1) out.push(min + ((max - min) * i) / (count - 1));
  return out;
};

const autoRange = (values, fallbackSpan = 1) => {
  const clean = values.filter((v) => Number.isFinite(v));
  if (!clean.length) return [-fallbackSpan, fallbackSpan];
  const min = Math.min(...clean);
  const max = Math.max(...clean);
  if (Math.abs(max - min) < 1e-10) {
    const mid = (min + max) / 2;
    const span = Math.max(Math.abs(mid) * 0.2, 0.02, fallbackSpan * 0.1);
    return [mid - span, mid + span];
  }
  const pad = (max - min) * 0.12;
  return [min - pad, max + pad];
};

const buildPath = (values, toX, toY) => {
  let d = '';
  let open = false;
  values.forEach((v, i) => {
    if (!Number.isFinite(v)) {
      open = false;
      return;
    }
    d += `${open ? 'L' : 'M'} ${toX(i)} ${toY(v)} `;
    open = true;
  });
  return d.trim();
};

function DualAxisChart({ series }) {
  const host = useRef(null);
  const [width, setWidth] = useState(900);

  useEffect(() => {
    if (!host.current) return undefined;
    const ro = new ResizeObserver(() => {
      const next = Math.floor(host.current?.clientWidth || 900);
      setWidth((prev) => (Math.abs(prev - next) > 1 ? next : prev));
    });
    ro.observe(host.current);
    return () => ro.disconnect();
  }, []);

  if (!series.length) {
    return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无详情数据" />;
  }

  const innerW = Math.max(10, width - PAD.left - PAD.right);
  const innerH = 232;

  const basis = series.map((x) => num(x.basis_pct, NaN));
  const funding = series.map((x) =>
    x.funding_rate_pct == null ? NaN : num(x.funding_rate_pct, NaN)
  );

  const [leftMin, leftMax] = autoRange(basis, 0.4);
  const [rightMin, rightMax] = autoRange(funding, 0.06);
  const leftTicks = makeTicks(leftMin, leftMax, 5);
  const rightTicks = makeTicks(rightMin, rightMax, 5);

  const toX = (i) => PAD.left + (innerW * i) / Math.max(1, series.length - 1);
  const toYLeft = (v) => PAD.top + innerH * (1 - (v - leftMin) / Math.max(1e-12, leftMax - leftMin));
  const toYRight = (v) =>
    PAD.top + innerH * (1 - (v - rightMin) / Math.max(1e-12, rightMax - rightMin));

  const basisPath = buildPath(basis, toX, toYLeft);
  const fundingPath = buildPath(funding, toX, toYRight);
  const xLabels = [...new Set([0, Math.floor((series.length - 1) / 2), series.length - 1])];

  return (
    <div ref={host} style={{ width: '100%' }}>
      <svg width={width} height={300}>
        {leftTicks.map((t) => (
          <line
            key={`grid-${t}`}
            x1={PAD.left}
            x2={PAD.left + innerW}
            y1={toYLeft(t)}
            y2={toYLeft(t)}
            stroke="#e2e8f0"
            strokeDasharray="3 3"
          />
        ))}

        <line x1={PAD.left} x2={PAD.left} y1={PAD.top} y2={PAD.top + innerH} stroke="#cbd5e1" />
        <line
          x1={PAD.left + innerW}
          x2={PAD.left + innerW}
          y1={PAD.top}
          y2={PAD.top + innerH}
          stroke="#cbd5e1"
        />

        <path d={basisPath} fill="none" stroke="#f59e0b" strokeWidth="2" />
        <path d={fundingPath} fill="none" stroke="#06b6d4" strokeWidth="2" />

        {series.length === 1 && Number.isFinite(basis[0]) && (
          <circle cx={toX(0)} cy={toYLeft(basis[0])} r="3" fill="#f59e0b" />
        )}
        {series.length === 1 && Number.isFinite(funding[0]) && (
          <circle cx={toX(0)} cy={toYRight(funding[0])} r="3" fill="#06b6d4" />
        )}

        {leftTicks.map((t) => (
          <text
            key={`ly-${t}`}
            x={PAD.left - 8}
            y={toYLeft(t) + 4}
            textAnchor="end"
            fill="#f59e0b"
            fontSize={11}
          >
            {pctText(t, 3)}
          </text>
        ))}
        {rightTicks.map((t) => (
          <text
            key={`ry-${t}`}
            x={PAD.left + innerW + 8}
            y={toYRight(t) + 4}
            textAnchor="start"
            fill="#06b6d4"
            fontSize={11}
          >
            {pctText(t, 3)}
          </text>
        ))}

        {xLabels.map((idx) => (
          <text
            key={`tx-${idx}`}
            x={toX(idx)}
            y={PAD.top + innerH + 20}
            textAnchor="middle"
            fill="#64748b"
            fontSize={11}
          >
            {fmtTime(num(series[idx]?.time, NaN))}
          </text>
        ))}
      </svg>
    </div>
  );
}

function mergeHistory(payload) {
  const fundingSeries = (payload?.funding_series || [])
    .map((x) => ({
      t: num(x.time, NaN),
      v: x.rate_pct == null ? null : num(x.rate_pct, NaN),
    }))
    .filter((x) => Number.isFinite(x.t) && Number.isFinite(x.v))
    .sort((a, b) => a.t - b.t);

  let idx = 0;
  let last = null;
  return (payload?.series || []).map((x) => {
    const t = num(x.time, 0);
    while (idx < fundingSeries.length && fundingSeries[idx].t <= t) {
      last = fundingSeries[idx].v;
      idx += 1;
    }
    return { ...x, funding_rate_pct: last };
  });
}

function History({ row }) {
  const [timeframe, setTimeframe] = useState('1h');
  const [loading, setLoading] = useState(false);
  const [series, setSeries] = useState([]);
  const [err, setErr] = useState('');
  const reqRef = useRef(0);
  const rowKey = useMemo(() => keyOf(row), [row]);

  const load = useCallback(
    async (tf, force = false) => {
      const cacheKey = `${rowKey}|${tf}`;
      const cached = historyCache.get(cacheKey);
      if (!force && cached && Date.now() - cached.ts <= HISTORY_CACHE_TTL_MS) {
        setSeries(cached.series);
        setErr('');
        return;
      }

      reqRef.current += 1;
      const reqId = reqRef.current;
      setLoading(true);
      setErr('');
      try {
        const { data } = await getSpotBasisHistory({
          symbol: row.symbol,
          perp_exchange_id: row.perp_exchange_id,
          spot_exchange_id: row.spot_exchange_id,
          timeframe: tf,
          limit: 260,
        });
        if (reqRef.current !== reqId) return;
        const merged = mergeHistory(data);
        setSeries(merged);
        historyCache.set(cacheKey, { ts: Date.now(), series: merged });
      } catch (e) {
        if (reqRef.current !== reqId) return;
        setErr(e?.response?.data?.detail?.message || e?.message || '加载失败');
      } finally {
        if (reqRef.current === reqId) setLoading(false);
      }
    },
    [row, rowKey]
  );

  useEffect(() => {
    load(timeframe, false);
  }, [load, timeframe]);

  return (
    <div style={{ padding: 8, background: '#f8fafc', borderRadius: 8 }}>
      <Space style={{ marginBottom: 8 }} wrap>
        <Tag color="blue">{row.symbol}</Tag>
        <Tag>{row.perp_exchange_name} 合约</Tag>
        <Tag>{row.spot_exchange_name} 现货</Tag>
        <Segmented
          size="small"
          value={timeframe}
          onChange={setTimeframe}
          options={[
            { label: '5m', value: '5m' },
            { label: '15m', value: '15m' },
            { label: '1h', value: '1h' },
            { label: '4h', value: '4h' },
          ]}
        />
        <Button size="small" icon={<ReloadOutlined />} onClick={() => load(timeframe, true)}>
          刷新
        </Button>
        {loading && <Tag color="processing">加载中</Tag>}
        {err && <Tag color="error">{err}</Tag>}
      </Space>

      <Space size={14} style={{ marginBottom: 6 }}>
        <Space size={6}>
          <span
            style={{
              display: 'inline-block',
              width: 12,
              height: 3,
              borderRadius: 2,
              background: '#f59e0b',
            }}
          />
          <span style={{ color: '#475569', fontSize: 12 }}>基差(%) 左轴</span>
        </Space>
        <Space size={6}>
          <span
            style={{
              display: 'inline-block',
              width: 12,
              height: 3,
              borderRadius: 2,
              background: '#06b6d4',
            }}
          />
          <span style={{ color: '#475569', fontSize: 12 }}>费率(%) 右轴</span>
        </Space>
      </Space>

      <DualAxisChart series={series} />
    </div>
  );
}

function strictFallback(r) {
  const periods = Math.max(1, num(r.periods_per_day, 1));
  const expected24 = num(r.funding_rate_pct, 0) * periods;
  const feeAmortized = num(r.fee_round_trip_pct, 0) / 2;
  const basisPenalty = Math.max(0, Math.abs(num(r.basis_pct, 0)) - 0.35) * 0.18;
  const minVol = Math.max(1, Math.min(num(r.perp_volume_24h, 0), num(r.spot_volume_24h, 0)));
  const impactPct = clamp((50000 / minVol) * 100, 0, 0.35);
  const liquidityPenalty = impactPct * 0.6;
  const switchCost = feeAmortized * 0.35 + 0.01;
  const riskPenalty = basisPenalty + liquidityPenalty;
  const e24Net = expected24 - feeAmortized - switchCost - riskPenalty;

  const confidence = clamp(
    0.2 + (num(r.funding_rate_pct, 0) > 0 ? 0.2 : 0) + (e24Net > 0 ? 0.2 : 0),
    0.01,
    1
  );
  const capacity = clamp(
    0.6 * clamp(minVol / 25000000, 0, 1) + 0.4 * clamp(1 - impactPct / 0.35, 0, 1),
    0.01,
    1
  );
  const score = e24Net * confidence * capacity;
  return {
    e24_net_pct: Number(e24Net.toFixed(6)),
    confidence,
    capacity,
    score_model: Number(score.toFixed(6)),
    strict_components: {
      expected_24h_gross_pct: Number(expected24.toFixed(6)),
      fee_amortized_pct_day: Number(feeAmortized.toFixed(6)),
      switch_cost_pct_day: Number(switchCost.toFixed(6)),
      risk_penalty_pct_day: Number(riskPenalty.toFixed(6)),
      liquidity_penalty_pct_day: Number(liquidityPenalty.toFixed(6)),
      basis_risk_penalty_pct_day: Number(basisPenalty.toFixed(6)),
      impact_pct: Number(impactPct.toFixed(6)),
      hold_days_assumption: 2,
    },
    steady_stats: { n: 0 },
  };
}

function normalizeRow(r) {
  if (r?.score_strict != null || r?.e24_net_pct_strict != null) {
    return {
      ...r,
      e24_net_pct: num(r.e24_net_pct_strict, 0),
      confidence: clamp(num(r.confidence_strict, 0), 0, 1),
      capacity: clamp(num(r.capacity_strict, 0), 0, 1),
      score_model: num(r.score_strict, 0),
      strict_components: r.strict_components || {},
      steady_stats: r.steady_stats || {},
    };
  }
  return { ...r, ...strictFallback(r) };
}


export default function SpotBasisAuto() {
  const [rows, setRows] = useState([]);
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState([]);
  const [cfg, setCfg] = useState(null);
  const [saving, setSaving] = useState(false);
  const [savingStatus, setSavingStatus] = useState(false);
  const [decisionPreview, setDecisionPreview] = useState(null);
  const [cycleLogs, setCycleLogs] = useState([]);
  const [cycleRunning, setCycleRunning] = useState(false);
  const [drawdownWatermarkResetting, setDrawdownWatermarkResetting] = useState(false);
  const [exchangeFundsRefreshing, setExchangeFundsRefreshing] = useState(false);
  const cycleLastQuery = useSpotBasisAutoCycleLastQuery();
  const cycleLogsQuery = useSpotBasisAutoCycleLogsQuery(160);
  const drawdownWatermarkQuery = useSpotBasisDrawdownWatermarkQuery();
  const exchangeFundsQuery = useSpotBasisAutoExchangeFundsQuery();
  const cycleLast = cycleLastQuery.data || null;
  const drawdownWatermark = drawdownWatermarkQuery.data || null;
  const drawdownWatermarkLoading = drawdownWatermarkQuery.isPending;
  const exchangeFunds = exchangeFundsQuery.data || [];
  const exchangeFundsLoading = exchangeFundsQuery.isPending || exchangeFundsRefreshing;

  const exchangeOptions = useMemo(
    () =>
      exchanges.map((x) => ({
        label: x.display_name || x.name || `EX#${x.id}`,
        value: x.id,
      })),
    [exchanges]
  );

  const [filters, setFilters] = useState({
    symbol: '',
    min_rate: 0.01,
    min_perp_volume: 1000000,
    min_spot_volume: 1000000,
    min_basis_pct: 0,
    perp_exchange_ids: [],
    spot_exchange_ids: [],
    require_cross_exchange: false,
    action_mode: 'open',
    sort_by: 'score_strict',
  });
  const exchangesQuery = useSpotBasisAutoActiveExchangesQuery();
  const exchanges = exchangesQuery.data || [];
  const opportunitiesQuery = useSpotBasisAutoOpportunitiesQuery(filters, expanded.length === 0);
  const decisionPreviewQuery = useSpotBasisAutoDecisionPreviewQuery(filters);
  const decisionLoading = decisionPreviewQuery.isPending;
  const rowsLoading = opportunitiesQuery.isPending || loading;

  const loadCfg = useCallback(async () => {
    const [cfgRes, statusRes] = await Promise.allSettled([
      getSpotBasisAutoConfig(),
      getSpotBasisAutoStatus(),
    ]);

    const c = cfgRes.status === 'fulfilled' ? cfgRes.value?.data || {} : {};
    const s = statusRes.status === 'fulfilled' ? statusRes.value?.data || {} : {};

    const merged = {
      ...DEFAULT_CFG,
      ...(c || {}),
      is_enabled: typeof s?.enabled === 'boolean' ? !!s.enabled : !!c?.is_enabled,
      dry_run: typeof s?.dry_run === 'boolean' ? !!s.dry_run : !!c?.dry_run,
    };
    setCfg(merged);

    if (cfgRes.status === 'rejected' && statusRes.status === 'rejected') {
      throw cfgRes.reason || statusRes.reason || new Error('配置接口不可用');
    }
  }, []);

  const refreshRows = useCallback(
    async (silent = false) => {
      if (!silent) setLoading(true);
      try {
        const res = await opportunitiesQuery.refetch();
        if (res.data) {
          setRows(res.data.map(normalizeRow));
        }
        if (res.error && !silent) {
          message.error(errText(res.error, '机会列表加载失败'));
        }
      } finally {
        if (!silent) setLoading(false);
      }
    },
    [opportunitiesQuery]
  );

  const refreshDecisionPreview = useCallback(
    async (silent = false) => {
      const res = await decisionPreviewQuery.refetch();
      if (res.data) {
        setDecisionPreview(res.data);
      }
      if (res.error && !silent) {
        message.error(errText(res.error, '决策预览加载失败'));
        setDecisionPreview(null);
      }
    },
    [decisionPreviewQuery]
  );

  useEffect(() => {
    loadCfg().catch((e) => message.error(errText(e, '自动策略配置加载失败')));
  }, [loadCfg]);

  useEffect(() => {
    if (cycleLogsQuery.data) {
      setCycleLogs(cycleLogsQuery.data);
    }
  }, [cycleLogsQuery.data]);

  useEffect(() => {
    if (opportunitiesQuery.data) {
      setRows(opportunitiesQuery.data.map(normalizeRow));
    }
  }, [opportunitiesQuery.data]);

  useEffect(() => {
    if (decisionPreviewQuery.data) {
      setDecisionPreview(decisionPreviewQuery.data);
    }
  }, [decisionPreviewQuery.data]);

  const stats = useMemo(() => {
    if (!rows.length) return { c: 0, e: 0, s: 0 };
    return {
      c: rows.length,
      e: rows.reduce((a, b) => a + num(b.e24_net_pct, 0), 0) / rows.length,
      s: Math.max(...rows.map((x) => num(x.score_model, 0))),
    };
  }, [rows]);

  const fundsSummary = useMemo(() => {
    const totalUsdt = exchangeFunds.reduce((acc, x) => acc + num(x.total_usdt, 0), 0);
    const currentNotional = exchangeFunds.reduce((acc, x) => acc + num(x.current_notional, 0), 0);
    const maxNotional = exchangeFunds.reduce((acc, x) => acc + num(x.max_notional, 0), 0);
    const usedPct = maxNotional > 0 ? (currentNotional / maxNotional) * 100 : 0;
    return {
      totalUsdt,
      currentNotional,
      maxNotional,
      usedPct,
    };
  }, [exchangeFunds]);

  const setCfgField = useCallback((key, value) => {
    const meta = CFG_FIELD_META[key] || {};
    setCfg((prev) => {
      const base = prev || DEFAULT_CFG;
      const fallback = num(base?.[key], 0);
      let next = num(value, fallback);
      if (meta.int) next = Math.trunc(next);
      if (Number.isFinite(meta.min)) next = Math.max(meta.min, next);
      if (Number.isFinite(meta.max)) next = Math.min(meta.max, next);
      return { ...base, [key]: next };
    });
  }, []);

  const saveCfg = async () => {
    if (!cfg) return;
    setSaving(true);
    try {
      const payload = {};
      Object.keys(DEFAULT_CFG).forEach((k) => {
        if (cfg[k] !== undefined) payload[k] = cfg[k];
      });
      await updateSpotBasisAutoConfig(payload);
      await loadCfg();
      message.success('参数已保存');
    } finally {
      setSaving(false);
    }
  };

  const setStatus = async (enabled, dryRun) => {
    setSavingStatus(true);
    try {
      await setSpotBasisAutoStatus({ enabled, dry_run: dryRun });
      setCfg((p) => ({ ...(p || DEFAULT_CFG), is_enabled: enabled, dry_run: dryRun }));
      if (enabled) message.success('自动程序已启用');
    } catch (e) {
      message.error(errText(e, '状态更新失败'));
      await loadCfg();
    } finally {
      setSavingStatus(false);
    }
  };

  const runCycleOnce = async () => {
    setCycleRunning(true);
    try {
      await runSpotBasisAutoCycleOnce();
      await Promise.all([
        refreshRows(true),
        refreshDecisionPreview(true),
        cycleLastQuery.refetch(),
        cycleLogsQuery.refetch(),
        drawdownWatermarkQuery.refetch(),
        exchangeFundsQuery.refetch(),
      ]);
      message.success('周期执行完成');
    } catch (e) {
      message.error(errText(e, '操作失败'));
    } finally {
      setCycleRunning(false);
    }
  };

  const resetDrawdownWatermark = async () => {
    setDrawdownWatermarkResetting(true);
    try {
      const { data } = await resetSpotBasisDrawdownWatermark();
      await Promise.all([drawdownWatermarkQuery.refetch(), cycleLastQuery.refetch()]);
      message.success(`高水位已重置到 ${fmtUsd(num(data?.peak_nav_usdt, 0), 2)}`);
    } catch (e) {
      message.error(errText(e, '重置高水位失败'));
    } finally {
      setDrawdownWatermarkResetting(false);
    }
  };

  const refreshExchangeFunds = async () => {
    setExchangeFundsRefreshing(true);
    try {
      const res = await exchangeFundsQuery.refetch();
      if (res.error) {
        message.error(errText(res.error, '交易所资金加载失败'));
      }
    } finally {
      setExchangeFundsRefreshing(false);
    }
  };

  const refreshCycleLogs = async () => {
    const res = await cycleLogsQuery.refetch();
    if (res.error) {
      message.error(errText(res.error, '日志加载失败'));
    }
  };

  const columns = [
    {
      title: '交易对',
      dataIndex: 'symbol',
      width: 170,
      render: (v, r) => (
        <Space>
          <Tag color="cyan">{v}</Tag>
          <Tag>{r.spot_symbol}</Tag>
        </Space>
      ),
    },
    {
      title: '合约腿',
      dataIndex: 'perp_exchange_name',
      width: 130,
      render: (_, r) => (
        <div>
          <Tag color="orange">{r.perp_exchange_name}</Tag>
          <div style={{ color: '#64748b', fontSize: 12 }}>{fmtPrice(r.perp_price)}</div>
        </div>
      ),
    },
    {
      title: '现货腿',
      dataIndex: 'spot_exchange_name',
      width: 130,
      render: (_, r) => (
        <div>
          <Tag color="green">{r.spot_exchange_name}</Tag>
          <div style={{ color: '#64748b', fontSize: 12 }}>{fmtPrice(r.spot_price)}</div>
        </div>
      ),
    },
    {
      title: '资金费率',
      dataIndex: 'funding_rate_pct',
      width: 100,
      render: (v) => <span style={{ color: '#dc2626', fontWeight: 600 }}>{pctText(v, 4)}</span>,
      sorter: (a, b) => num(a.funding_rate_pct) - num(b.funding_rate_pct),
    },
    {
      title: '基差',
      dataIndex: 'basis_pct',
      width: 100,
      render: (v) => <span style={{ color: '#f59e0b', fontWeight: 600 }}>{pctText(v, 4)}</span>,
      sorter: (a, b) => num(a.basis_pct) - num(b.basis_pct),
    },
    {
      title: 'E24净期望',
      dataIndex: 'e24_net_pct',
      width: 120,
      render: (v) => (
        <span style={{ color: num(v) >= 0 ? '#059669' : '#dc2626', fontWeight: 700 }}>{pctText(v, 4)}</span>
      ),
      sorter: (a, b) => num(a.e24_net_pct) - num(b.e24_net_pct),
      defaultSortOrder: 'descend',
    },
    {
      title: '置信度',
      dataIndex: 'confidence',
      width: 110,
      render: (v, r) => (
        <div>
          <div>{(num(v, 0) * 100).toFixed(1)}%</div>
          <div style={{ color: '#64748b', fontSize: 12 }}>n={num(r?.steady_stats?.n, 0)}</div>
        </div>
      ),
      sorter: (a, b) => num(a.confidence) - num(b.confidence),
    },
    {
      title: '容量',
      dataIndex: 'capacity',
      width: 110,
      render: (v) => `${(num(v, 0) * 100).toFixed(1)}%`,
      sorter: (a, b) => num(a.capacity) - num(b.capacity),
    },
    {
      title: '综合评分',
      dataIndex: 'score_model',
      width: 100,
      render: (v) => <span style={{ color: '#2563eb', fontWeight: 700 }}>{num(v, 0).toFixed(4)}</span>,
      sorter: (a, b) => num(a.score_model) - num(b.score_model),
    },
    {
      title: '24h成交量',
      key: 'vol',
      width: 130,
      render: (_, r) => (
        <div>
          <div>合约 {fmtVol(r.perp_volume_24h)}</div>
          <div style={{ color: '#64748b' }}>现货 {fmtVol(r.spot_volume_24h)}</div>
        </div>
      ),
      sorter: (a, b) =>
        Math.min(num(a.perp_volume_24h, 0), num(a.spot_volume_24h, 0)) -
        Math.min(num(b.perp_volume_24h, 0), num(b.spot_volume_24h, 0)),
    },
  ];

  const exchangeFundsColumns = [
    {
      title: '交易所',
      dataIndex: 'exchange_name',
      width: 120,
      render: (v, r) => (
        <Space direction="vertical" size={0}>
          <span style={{ fontWeight: 600 }}>{v}</span>
          {r.unified_account ? <Tag color="blue">统一账户</Tag> : <Tag>分账户</Tag>}
        </Space>
      ),
    },
    {
      title: '总资金',
      dataIndex: 'total_usdt',
      width: 110,
      render: (v) => <span>{fmtUsd(v, 2)}</span>,
      sorter: (a, b) => num(a.total_usdt) - num(b.total_usdt),
    },
    {
      title: '现货/合约',
      key: 'split',
      width: 130,
      render: (_, r) => (
        <Space direction="vertical" size={0}>
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            现货 {fmtUsd(r.spot_usdt, 2)}
          </Typography.Text>
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            合约 {fmtUsd(r.futures_usdt, 2)}
          </Typography.Text>
        </Space>
      ),
    },
    {
      title: '名义占用',
      key: 'margin',
      width: 128,
      render: (_, r) => (
        <Space direction="vertical" size={0}>
          <Typography.Text style={{ fontSize: 12 }}>
            {fmtUsd(r.current_notional, 0)} / {fmtUsd(r.max_notional, 0)}
          </Typography.Text>
          <Typography.Text type="secondary" style={{ fontSize: 12 }}>
            利用率 {num(r.used_pct, 0).toFixed(1)}%
          </Typography.Text>
        </Space>
      ),
    },
    {
      title: '状态',
      key: 'status',
      width: 128,
      render: (_, r) => {
        if (r.error) return <Tag color="error">异常</Tag>;
        if (r.warning) return <Tag color="warning">部分可用</Tag>;
        return <Tag color="success">正常</Tag>;
      },
    },
  ];

  const cycleLogColumns = [
    {
      title: '时间',
      dataIndex: 'ts',
      width: 118,
      render: (v) => <Typography.Text type="secondary">{fmtTime(num(v, 0) * 1000)}</Typography.Text>,
      sorter: (a, b) => num(a.ts, 0) - num(b.ts, 0),
      defaultSortOrder: 'descend',
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 110,
      render: (v) => <Tag color={cycleStatusColor(v)}>{cycleStatusLabel(v)}</Tag>,
    },
    {
      title: '轮次',
      dataIndex: 'mode',
      width: 140,
      render: (v) => cycleModeTag(v),
    },
    {
      title: '摘要',
      key: 'summary',
      render: (_, r) => <Typography.Text>{cycleSummaryText(r)}</Typography.Text>,
    },
  ];

  return (
    <div style={{ padding: 12, background: '#f5f7fb', minHeight: '100%' }}>
      <Row gutter={[12, 12]}>
        <Col span={16}>
          <Card style={{ marginBottom: 12 }}>
            <Space wrap>
              <Input
                style={{ width: 240 }}
                placeholder="搜索交易对"
                prefix={<SearchOutlined />}
                value={filters.symbol}
                onChange={(e) => setFilters((f) => ({ ...f, symbol: e.target.value }))}
              />
              <InputNumber
                addonBefore="费率%"
                value={filters.min_rate}
                min={0}
                step={0.001}
                onChange={(v) => setFilters((f) => ({ ...f, min_rate: num(v, 0) }))}
              />
              <InputNumber
                addonBefore="合约量"
                value={filters.min_perp_volume}
                min={0}
                step={100000}
                onChange={(v) => setFilters((f) => ({ ...f, min_perp_volume: num(v, 0) }))}
              />
              <InputNumber
                addonBefore="现货量"
                value={filters.min_spot_volume}
                min={0}
                step={100000}
                onChange={(v) => setFilters((f) => ({ ...f, min_spot_volume: num(v, 0) }))}
              />
              <InputNumber
                addonBefore="基差%"
                value={filters.min_basis_pct}
                min={-10}
                step={0.01}
                onChange={(v) => setFilters((f) => ({ ...f, min_basis_pct: num(v, 0) }))}
              />
              <Select
                mode="multiple"
                allowClear
                style={{ width: 220 }}
                placeholder="合约交易所"
                value={filters.perp_exchange_ids}
                options={exchangeOptions}
                onChange={(v) => setFilters((f) => ({ ...f, perp_exchange_ids: v || [] }))}
              />
              <Select
                mode="multiple"
                allowClear
                style={{ width: 220 }}
                placeholder="现货交易所"
                value={filters.spot_exchange_ids}
                options={exchangeOptions}
                onChange={(v) => setFilters((f) => ({ ...f, spot_exchange_ids: v || [] }))}
              />
              <Select
                style={{ width: 180 }}
                value={filters.sort_by}
                options={[
                  { label: '严格综合评分', value: 'score_strict' },
                  { label: '资金费率', value: 'funding_rate_pct' },
                  { label: '基差', value: 'basis_abs' },
                  { label: 'E24净期望', value: 'e24_net_pct' },
                ]}
                onChange={(v) => setFilters((f) => ({ ...f, sort_by: v || 'score_strict' }))}
              />
              <Button icon={<ReloadOutlined />} type="primary" onClick={() => { void refreshRows(false); }} loading={rowsLoading}>
                刷新
              </Button>
            </Space>
          </Card>

          <Row gutter={[12, 12]} style={{ marginBottom: 12 }}>
            <Col span={8}>
              <Card>
                <Statistic title="监控标的" value={stats.c} />
              </Card>
            </Col>
            <Col span={8}>
              <Card>
                <Statistic title="平均E24净期望" value={Number(num(stats.e, 0).toFixed(4))} suffix="%" />
              </Card>
            </Col>
            <Col span={8}>
              <Card>
                <Statistic title="最高综合评分" value={Number(num(stats.s, 0).toFixed(4))} />
              </Card>
            </Col>
          </Row>

          <Card title={<Space>机会列表 <Tag color="blue">{rows.length}</Tag> <Tag>{STRICT_HINT}</Tag></Space>}>
            <Table
              size="small"
              rowKey={keyOf}
              loading={rowsLoading}
              dataSource={rows}
              columns={columns}
              pagination={{ pageSize: 20, showSizeChanger: false }}
              expandable={{
                expandedRowKeys: expanded,
                onExpandedRowsChange: (keys) => setExpanded((keys || []).map((k) => String(k))),
                expandedRowRender: (record) => <History key={keyOf(record)} row={record} />,
              }}
              scroll={{ x: 1500 }}
              locale={{
                emptyText: rowsLoading ? <Spin /> : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无机会" />,
              }}
            />
          </Card>
        </Col>

        <Col span={8}>
          <Card title={<Space><RobotOutlined />{termLabel('自动策略控制', AUTO_TERM_HELP.auto_control)}</Space>} style={{ marginBottom: 12 }}>
            {!cfg ? (
              <Spin />
            ) : (
              <Space direction="vertical" style={{ width: '100%' }}>
                <Row justify="space-between">
                  {termLabel('启用自动策略', AUTO_TERM_HELP.is_enabled)}
                  <Switch
                    checked={!!cfg.is_enabled}
                    loading={savingStatus}
                    onChange={(v) => setStatus(v, !!cfg.dry_run)}
                  />
                </Row>
                <Row justify="space-between">
                  {termLabel('模拟模式', AUTO_TERM_HELP.dry_run)}
                  <Switch checked={!!cfg.dry_run} loading={savingStatus} onChange={(v) => setStatus(!!cfg.is_enabled, v)} />
                </Row>
                <Row justify="space-between">
                  {termLabel('敞口修复失败熔断', AUTO_TERM_HELP.circuit_breaker_on_repair_fail)}
                  <Switch
                    checked={!!cfg.circuit_breaker_on_repair_fail}
                    onChange={(v) => setCfg((p) => ({ ...(p || DEFAULT_CFG), circuit_breaker_on_repair_fail: !!v }))}
                  />
                </Row>
                <Typography.Text type="secondary">
                  {termLabel('合约开仓执行', AUTO_TERM_HELP.contract_entry_execution)}: {termLabel('全仓模式', AUTO_TERM_HELP.cross_margin_mode)} / {termLabel('固定杠杆 2x', AUTO_TERM_HELP.fixed_leverage_2x)}
                </Typography.Text>
                <Typography.Text type="secondary">
                  {termLabel('资金安全垫', AUTO_TERM_HELP.safety_cushion)} = max(下限, 手续费缓冲 + 滑点缓冲 + 保证金缓冲)
                </Typography.Text>
                <Typography.Text type="secondary">
                  {termLabel('无敞口容忍', AUTO_TERM_HELP.unhedged_tolerance)} = max(绝对USDT阈值, NAV百分比阈值)
                </Typography.Text>
                <Card size="small" title={termLabel('组合回撤高水位', AUTO_TERM_HELP.drawdown_watermark)}>
                  <Space direction="vertical" style={{ width: '100%' }} size={4}>
                    {drawdownWatermarkLoading ? (
                      <Spin size="small" />
                    ) : (
                      <>
                        <Typography.Text type="secondary">
                          当前高水位: {fmtUsd(drawdownWatermark?.peak_nav_usdt, 2)}
                        </Typography.Text>
                        <Typography.Text type="secondary">
                          当前 NAV: {fmtUsd(drawdownWatermark?.current_nav_usdt, 2)}
                        </Typography.Text>
                        <Typography.Text type="secondary">
                          最近重置: {fmtIsoTime(drawdownWatermark?.drawdown_peak_reset_at)}
                        </Typography.Text>
                      </>
                    )}
                    <Popconfirm
                      title="重置高水位"
                      description={`${AUTO_TERM_HELP.drawdown_reset_button} 确认继续？`}
                      okText="确认"
                      cancelText="取消"
                      onConfirm={resetDrawdownWatermark}
                      disabled={drawdownWatermarkResetting}
                    >
                      <Button
                        danger
                        loading={drawdownWatermarkResetting}
                        disabled={drawdownWatermarkLoading}
                        block
                      >
                        重置高水位
                      </Button>
                    </Popconfirm>
                  </Space>
                </Card>
                {CFG_SECTIONS.map((section) => (
                  <Card key={section.title} size="small" title={termLabel(section.title, AUTO_TERM_HELP[section.title])}>
                    <Space direction="vertical" style={{ width: '100%' }}>
                      {section.keys.map((k) => {
                        const meta = CFG_FIELD_META[k] || {};
                        return (
                          <InputNumber
                            key={k}
                            style={{ width: '100%' }}
                            addonBefore={termLabel(meta.label || k, meta.help || AUTO_TERM_HELP[k])}
                            addonAfter={meta.addonAfter}
                            value={cfg[k]}
                            min={meta.min}
                            max={meta.max}
                            step={meta.step ?? 1}
                            precision={meta.int ? 0 : undefined}
                            onChange={(v) => setCfgField(k, v)}
                          />
                        );
                      })}
                    </Space>
                  </Card>
                ))}
                <Button type="primary" icon={<SaveOutlined />} onClick={saveCfg} loading={saving} block>
                  保存参数
                </Button>
                <Button onClick={runCycleOnce} loading={cycleRunning} block>
                  立即执行一次
                </Button>
              </Space>
            )}
          </Card>

          <Card
            title="交易所资金监控"
            size="small"
            style={{ marginBottom: 12 }}
            extra={
              <Button
                size="small"
                icon={<ReloadOutlined />}
                onClick={() => { void refreshExchangeFunds(); }}
                loading={exchangeFundsLoading}
              >
                刷新
              </Button>
            }
          >
            <Space direction="vertical" size={8} style={{ width: '100%' }}>
              <Typography.Text type="secondary">
                总资金 {fmtUsd(fundsSummary.totalUsdt, 2)}，组合名义占用 {fmtUsd(fundsSummary.currentNotional, 0)} / {fmtUsd(fundsSummary.maxNotional, 0)}
                （{num(fundsSummary.usedPct, 0).toFixed(1)}%）
              </Typography.Text>
              <Table
                size="small"
                rowKey={(r) => String(r.exchange_id)}
                loading={exchangeFundsLoading}
                dataSource={exchangeFunds}
                columns={exchangeFundsColumns}
                pagination={false}
                scroll={{ x: 620, y: 260 }}
                locale={{
                  emptyText: exchangeFundsLoading ? <Spin /> : <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无资金数据" />,
                }}
              />
            </Space>
          </Card>

          <Card title="最近周期" size="small" style={{ marginBottom: 12 }}>
            {!cycleLast ? (
              <Typography.Text type="secondary">暂无周期记录</Typography.Text>
            ) : (
              <Space direction="vertical" size={4} style={{ width: '100%' }}>
                <Space wrap size={6}>
                  <Tag color={cycleStatusColor(cycleLast.status)}>
                    状态: {cycleStatusLabel(cycleLast.status)}
                  </Tag>
                  {cycleModeTag(cycleLast.mode)}
                  <Tag>模拟模式: {cycleLast.dry_run ? '是' : '否'}</Tag>
                </Space>
                <Typography.Text type="secondary">计划开仓 {num(cycleLast.open_plan_pairs, 0)} / 平仓 {num(cycleLast.close_plan_pairs, 0)}</Typography.Text>
                <Typography.Text type="secondary">已完成开仓 {num(cycleLast.opened_pairs, 0)} / 平仓 {num(cycleLast.closed_pairs, 0)}</Typography.Text>
                <Typography.Text type="secondary">失败开仓 {num(cycleLast.open_failed_pairs, 0)} / 平仓 {num(cycleLast.close_failed_pairs, 0)}</Typography.Text>
                <Typography.Text type="secondary">重试队列待处理 {num(cycleLast.retry_queue?.pending, 0)}</Typography.Text>
                {!!cycleLast.execution_writeback && (
                  <Typography.Text type="secondary">
                    新增重试 平仓/开仓 {num(cycleLast.execution_writeback?.retry_enqueued_close, 0)}/
                    {num(cycleLast.execution_writeback?.retry_enqueued_open, 0)}
                  </Typography.Text>
                )}
                {!!cycleLast.retry_result && (
                  <Typography.Text type="secondary">
                    重试 到期/执行/成功/失败/丢弃: {num(cycleLast.retry_result?.due_count, 0)}/
                    {num(cycleLast.retry_result?.retried, 0)}/{num(cycleLast.retry_result?.succeeded, 0)}/
                    {num(cycleLast.retry_result?.failed, 0)}/{num(cycleLast.retry_result?.dropped, 0)}
                  </Typography.Text>
                )}
              </Space>
            )}
          </Card>

          <Card
            title="运行日志"
            size="small"
            style={{ marginBottom: 12 }}
            extra={
              <Space>
                <Button size="small" onClick={() => { void refreshCycleLogs(); }}>
                  刷新
                </Button>
                <Button size="small" danger onClick={() => setCycleLogs([])}>
                  清空
                </Button>
              </Space>
            }
          >
            <Table
              size="small"
              rowKey={(r) => r.__key || `${num(r.ts, 0)}-${r.status || 's'}-${r.mode || 'm'}`}
              dataSource={cycleLogs}
              columns={cycleLogColumns}
              pagination={false}
              scroll={{ y: 260 }}
              locale={{
                emptyText: <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无运行日志" />,
              }}
            />
          </Card>

          <Card title="决策预览" size="small">
            {decisionLoading && !decisionPreview ? (
              <Spin />
            ) : !decisionPreview ? (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无预览" />
            ) : (
              <Space direction="vertical" size={6} style={{ width: '100%' }}>
                <Typography.Text type="secondary">{decisionPreview?.policy?.note || '--'}</Typography.Text>
                <Tag color={decisionPreview?.open_evaluation?.eligible ? 'success' : 'default'}>
                  {decisionPreview?.open_evaluation?.eligible ? '允许入场' : '禁止入场'}
                </Tag>
                <Typography.Text type="secondary">
                  候选数: {num(decisionPreview?.open_evaluation?.candidate_count, 0)}
                </Typography.Text>
              </Space>
            )}
          </Card>
        </Col>
      </Row>
    </div>
  );
}
