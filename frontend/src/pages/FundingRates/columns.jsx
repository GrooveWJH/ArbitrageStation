import React from 'react';
import {
  Tag,
  Tooltip,
} from 'antd';
import ExchangeLogoName from '../../components/ExchangeLogoName';
import { fmtTime } from '../../utils/time';

function signedPct(v, digits = 4) {
  const n = Number(v || 0);
  return `${n > 0 ? '+' : ''}${n.toFixed(digits)}%`;
}

function magnitudePct(v, digits = 4) {
  const n = Math.abs(Number(v || 0));
  return `${n.toFixed(digits)}%`;
}

function annualizedAbsFromRate(ratePct) {
  return Math.abs(Number(ratePct || 0)) * 3 * 365;
}

function volumeLabel(v) {
  if (!(v > 0)) return '-';
  if (v >= 1e9) return `${(v / 1e9).toFixed(1)}B`;
  if (v >= 1e6) return `${(v / 1e6).toFixed(1)}M`;
  return `${(v / 1e3).toFixed(0)}K`;
}

function absRateLevel(v) {
  const abs = Math.abs(Number(v || 0));
  if (abs >= 0.30) return 'is-high';
  if (abs >= 0.10) return 'is-mid';
  return 'is-low';
}

export function buildFundingColumns(exchanges = []) {
  return [
    {
      title: '交易对', dataIndex: 'symbol', key: 'symbol', fixed: 'left', width: 160,
      render: v => <Tag color="blue" className="kinetic-pair-chip">{v}</Tag>,
      sorter: (a, b) => a.symbol.localeCompare(b.symbol),
    },
    {
      title: '交易所', dataIndex: 'exchange_name', key: 'exchange_name', width: 120,
      render: (v, r) => (
        <Tag className="kinetic-exchange-chip">
          <ExchangeLogoName name={v} exchangeId={r.exchange_id} />
        </Tag>
      ),
      filters: exchanges.map(e => ({ text: e.display_name, value: e.display_name })),
      onFilter: (value, record) => record.exchange_name === value,
    },
    {
      title: '资金费率', dataIndex: 'rate_pct', key: 'rate_pct', width: 130,
      render: v => {
        const cls = v > 0 ? 'kinetic-num-negative' : v < 0 ? 'kinetic-num-positive' : 'kinetic-num-neutral';
        const label = v > 0 ? '多头付费' : v < 0 ? '空头付费' : '中性';
        return (
          <Tooltip title={label}>
          <span className={`kinetic-num ${cls}`}>{signedPct(v, 4)}</span>
          </Tooltip>
        );
      },
      sorter: (a, b) => a.rate_pct - b.rate_pct,
      defaultSortOrder: 'descend',
    },
    {
      title: '费率绝对值', dataIndex: 'rate_pct', key: 'abs_rate',
      render: v => <span className={`kinetic-rate-pill ${absRateLevel(v)}`}>{Math.abs(v).toFixed(4)}%</span>,
      sorter: (a, b) => Math.abs(a.rate_pct) - Math.abs(b.rate_pct),
      width: 130,
    },
    {
      title: '年化绝对值 (3次/天)', key: 'annualized',
      render: (_, r) => {
        const ann = annualizedAbsFromRate(r.rate_pct);
        const cls = ann > 0 ? 'kinetic-num-positive' : 'kinetic-num-neutral';
        return <span className={`kinetic-num ${cls}`}>{magnitudePct(ann, 1)}</span>;
      },
      sorter: (a, b) => annualizedAbsFromRate(a.rate_pct) - annualizedAbsFromRate(b.rate_pct),
      width: 140,
    },
    {
      title: '24h交易量(U)', dataIndex: 'volume_24h', key: 'volume_24h', width: 140,
      render: v => v > 0
        ? <span className="kinetic-num kinetic-num-volume">{volumeLabel(v)}</span>
        : <span className="kinetic-num kinetic-num-muted">-</span>,
      sorter: (a, b) => (a.volume_24h || 0) - (b.volume_24h || 0),
    },
    {
      title: '下次结算', dataIndex: 'next_funding_time', key: 'next_funding_time', width: 160,
      render: v => <span className="kinetic-time">{fmtTime(v)}</span>,
    },
  ];
}
