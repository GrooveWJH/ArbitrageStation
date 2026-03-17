import React from 'react';
import { QuestionCircleOutlined } from '@ant-design/icons';
import { Tag, Tooltip } from 'antd';

export const STRICT_HINT = '严格评分: 综合评分 = E24净期望 × 置信度 × 容量';

export const CYCLE_STATUS_LABELS = {
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

export const CYCLE_MODE_META = {
  retry_only: { label: '仅重试轮次', color: 'magenta' },
  hedge_repair_only: { label: '仅敞口修复轮次', color: 'cyan' },
  risk_reduce_only: { label: '仅风控降仓轮次', color: 'orange' },
  portfolio_rebalance: { label: '组合再平衡轮次', color: 'blue' },
};

export const num = (v, d = 0) => {
  const x = Number(v);
  return Number.isFinite(x) ? x : d;
};

export const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v));
export const pctText = (v, p = 4) => `${num(v, 0).toFixed(p)}%`;
export const keyOf = (r) => `${r.symbol}|${r.perp_exchange_id}|${r.spot_exchange_id}`;
export const fmtVol = (v) => (num(v) >= 1e6 ? `${(num(v) / 1e6).toFixed(2)}M` : `${num(v).toFixed(0)}`);
export const fmtPrice = (v) => (num(v) > 1 ? `$${num(v).toFixed(4)}` : `$${num(v).toFixed(8)}`);
export const fmtUsd = (v, p = 2) => `$${num(v, 0).toFixed(p)}`;

export const fmtTime = (ms) => {
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

export const fmtIsoTime = (iso) => {
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

export const fmtCountdown = (secs) => {
  const s = Math.max(0, Math.floor(num(secs, 0)));
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  if (h > 0) return `${h}小时 ${String(m).padStart(2, '0')}分`;
  return `${String(m).padStart(2, '0')}分 ${String(sec).padStart(2, '0')}秒`;
};

export const cycleStatusColor = (status) => {
  const s = String(status || '');
  if (s === 'error' || s.includes('failed') || s.includes('circuit_breaker')) return 'error';
  if (s === 'executed' || s.includes('executed')) return 'success';
  if (s === 'throttled' || s.includes('blocked') || s.includes('wait')) return 'warning';
  if (s === 'disabled') return 'default';
  return 'processing';
};

export const cycleStatusLabel = (status) => {
  const key = String(status || '');
  if (!key) return '--';
  return CYCLE_STATUS_LABELS[key] || '未知状态';
};

export const cycleModeLabel = (mode) => {
  const key = String(mode || '');
  if (!key) return '--';
  return CYCLE_MODE_META[key]?.label || '未知轮次';
};

export const cycleModeTag = (mode) => {
  const key = String(mode || '');
  if (!key) return <Tag>未标注轮次</Tag>;
  const meta = CYCLE_MODE_META[key];
  if (!meta) return <Tag title={key}>未知轮次</Tag>;
  return <Tag color={meta.color}>{meta.label}</Tag>;
};

export const cycleSummaryText = (item) => {
  const parts = [];
  parts.push(`轮次 ${cycleModeLabel(item?.mode)}`);
  parts.push(`计划开/平 ${num(item?.open_plan_pairs, 0)}/${num(item?.close_plan_pairs, 0)}`);
  parts.push(`执行开/平 ${num(item?.opened_pairs, 0)}/${num(item?.closed_pairs, 0)}`);
  const retryPending = num(item?.retry_queue?.pending, 0);
  if (retryPending > 0) parts.push(`重试待处理 ${retryPending}`);
  if (item?.error) parts.push(`错误 ${String(item.error)}`);
  return parts.join(' | ');
};

export const shortRowId = (rowId) => {
  const [symbol, perp, spot] = String(rowId || '').split('|');
  if (!symbol) return '--';
  return `${symbol} ${perp || '-'}->${spot || '-'}`;
};

export const termLabel = (label, help) => (
  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 4, whiteSpace: 'nowrap' }}>
    <span>{label}</span>
    <Tooltip title={help || `${label}说明`} placement="top">
      <QuestionCircleOutlined style={{ color: '#8c8c8c', fontSize: 12 }} />
    </Tooltip>
  </span>
);

export function strictFallback(r) {
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
  const confidence = clamp(0.2 + (num(r.funding_rate_pct, 0) > 0 ? 0.2 : 0) + (e24Net > 0 ? 0.2 : 0), 0.01, 1);
  const capacity = clamp(0.6 * clamp(minVol / 25000000, 0, 1) + 0.4 * clamp(1 - impactPct / 0.35, 0, 1), 0.01, 1);
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

export function normalizeRow(r) {
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
