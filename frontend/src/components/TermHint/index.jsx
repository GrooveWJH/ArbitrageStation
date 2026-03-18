import React from 'react';
import { Tooltip } from 'antd';
import { QuestionCircleOutlined } from '@ant-design/icons';

export const TERM_HINTS = {
  spread_pnl: '价差收益（已实现+未实现），按 USDT 统一折算。',
  funding_pnl: '资金费收益，来自资金费流水归因。missing 时不显示 0。',
  fee_usdt: '交易手续费成本，按成交额与费率计算，Total 中会减去。',
  total_pnl: '统一口径：Total = Spread + Funding - Fee。',
  total_pnl_pct: '收益率 = Total PnL / capital_base（策略保证金基数）。',
  funding_coverage: '资金费覆盖率 = captured / expected。用于判断资金费数据完整性。',
  funding_quality: '资金费质量：ok / partial / stale / missing / na（无应计事件）。',
  quality: '数据质量等级：ok / partial / stale / missing。',
  quality_reason: '质量原因代码，如 funding_api_no_data、cursor_gap_detected。',
  capital_base: '策略保证金基数（USDT），用于收益率计算。',
  current_annualized: '当前年化估算，基于当前资金费率与结算频次推算，不代表已实现收益。',
  unrealized_pnl: '未实现盈亏，按当前价格与入场价格计算，仓位未平前会波动。',
  realized_pnl: '已实现盈亏，来自已平仓成交现金流汇总。',
  started_count: '窗口内新启动策略数（created_at 落在窗口内）。',
  closed_count: '窗口内结束策略数（closed_at 落在窗口内）。',
  continued_count: '窗口开始前已存在且在窗口内延续的策略数。',
  attribution: '盈亏归因分解：按策略类型统计 strategy_count / pnl / ratio。',
  entry_local: '本地数据库记录的入场价。',
  entry_exchange: '交易所回读入场价，用于和本地入场价核对偏差。',
};

export function TermHint({ term }) {
  const text = TERM_HINTS[term];
  if (!text) return null;
  return (
    <Tooltip title={text}>
      <QuestionCircleOutlined style={{ marginLeft: 4, color: '#999' }} />
    </Tooltip>
  );
}

export function TermLabel({ label, term }) {
  return (
    <span>
      {label}
      <TermHint term={term} />
    </span>
  );
}
