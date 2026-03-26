import React from 'react';
import { Space, Tag, Tooltip } from 'antd';
import { ThunderboltOutlined, WarningOutlined } from '@ant-design/icons';
import ExchangeLogoName from '../../components/ExchangeLogoName';
import { fmtTime } from '../../utils/time';
import { TermLabel } from '../../components/TermHint';
import {
  formatCountdown,
  formatPairBase,
  formatVolume,
  getOpportunitySignal,
} from './utils';
import { LongCell, PriceDiffCell, ShortCell } from './OpportunityCells';

function signedPct(v, digits = 4) {
  const n = Number(v || 0);
  return `${n > 0 ? '+' : ''}${n.toFixed(digits)}%`;
}

function toneClass(v, { high = 0, medium = 0 } = {}) {
  const n = Number(v || 0);
  if (n < 0) return 'kinetic-num-negative';
  if (high > 0 && n >= high) return 'kinetic-num-strong';
  if (medium > 0 && n >= medium) return 'kinetic-num-positive';
  if (n > 0) return 'kinetic-num-positive';
  return 'kinetic-num-neutral';
}

function annualizedToneClass(v) {
  const n = Number(v || 0);
  if (n < 0) return 'kinetic-num-negative';
  if (n >= 250) return 'kinetic-num-positive';
  if (n >= 100) return 'kinetic-num-strong';
  if (n > 0) return 'kinetic-num-positive';
  return 'kinetic-num-neutral';
}

export function buildOppColumns() {
  return [
    {
      title: '信号',
      key: 'signal',
      width: 140,
      align: 'left',
      render: (_, r) => {
        const signal = getOpportunitySignal(r);
        if (signal === 'risk') {
          return (
            <Tag className="kinetic-opportunity-signal is-risk" icon={<WarningOutlined />}>
              风险
            </Tag>
          );
        }
        if (signal === 'hot') {
          return (
            <Tag className="kinetic-opportunity-signal is-hot" icon={<ThunderboltOutlined />}>
              高收益
            </Tag>
          );
        }
        return <span className="kinetic-opportunity-signal-empty">—</span>;
      },
    },
    {
      title: '交易对 · USDT',
      dataIndex: 'symbol',
      key: 'symbol',
      width: 184,
      align: 'left',
      render: (v) => <Tag color="blue" className="kinetic-pair-chip kinetic-opp-pair-chip">{formatPairBase(v)}</Tag>,
    },
    { title: '做多腿', key: 'long', align: 'left', render: (_, r) => <LongCell record={r} /> },
    { title: '做空腿', key: 'short', align: 'left', render: (_, r) => <ShortCell record={r} /> },
    {
      title: '费率差',
      dataIndex: 'rate_diff_pct',
      key: 'rate_diff_pct',
      width: 146,
      align: 'center',
      className: 'kinetic-col-numeric',
      render: (v) => <span className={`kinetic-num ${toneClass(v, { medium: 0.01 })}`}>{signedPct(v, 4)}</span>,
      sorter: (a, b) => a.rate_diff_pct - b.rate_diff_pct,
    },
    {
      title: <TermLabel label="年化" term="current_annualized" />,
      dataIndex: 'annualized_pct',
      key: 'annualized_pct',
      width: 146,
      align: 'center',
      className: 'kinetic-col-numeric',
      render: (v) => <span className={`kinetic-num ${annualizedToneClass(v)}`}>{signedPct(v, 2)}</span>,
      sorter: (a, b) => (a.annualized_pct || 0) - (b.annualized_pct || 0),
    },
    { title: '合约价差', key: 'price_diff_pct', width: 146, align: 'center', className: 'kinetic-col-numeric', render: (_, r) => <PriceDiffCell record={r} />, sorter: (a, b) => (a.price_diff_pct || 0) - (b.price_diff_pct || 0) },
    {
      title: '最小24h量',
      dataIndex: 'min_volume_24h',
      key: 'min_volume_24h',
      width: 152,
      align: 'center',
      className: 'kinetic-col-numeric',
      render: (v) => (v > 0 ? <span className="kinetic-num kinetic-num-volume">{formatVolume(v)}</span> : <span className="kinetic-num kinetic-num-muted">-</span>),
      sorter: (a, b) => (a.min_volume_24h || 0) - (b.min_volume_24h || 0),
    },
  ];
}

export function buildSpotOppColumns() {
  return [
    { title: '交易对 · USDT', dataIndex: 'symbol', key: 'symbol', render: (v) => <Tag color="blue">{formatPairBase(v)}</Tag> },
    {
      title: '交易所',
      key: 'exchange_name',
      render: (_, r) => (
        <Space size={4}>
          <Tag className="kinetic-exchange-chip">
            <ExchangeLogoName name={r.exchange_name} exchangeId={r.exchange_id} />
          </Tag>
          {r.has_spot_market === false && (
            <Tooltip title={`${r.symbol.split(':')[0]} 在 ${r.exchange_name} 无现货交易对，无法做现货对冲`}>
              <Tag color="red">无现货</Tag>
            </Tooltip>
          )}
        </Space>
      ),
    },
    {
      title: '资金费率',
      dataIndex: 'funding_rate_pct',
      key: 'funding_rate_pct',
      render: (v) => (
        <span className={`kinetic-num ${v > 0 ? 'kinetic-num-negative' : 'kinetic-num-positive'}`}>{signedPct(v, 4)}</span>
      ),
    },
    {
      title: <TermLabel label="年化" term="current_annualized" />,
      dataIndex: 'annualized_pct',
      key: 'annualized_pct',
      render: (v) => <span className={`kinetic-num ${annualizedToneClass(v)}`}>{signedPct(v, 2)}</span>,
      sorter: (a, b) => a.annualized_pct - b.annualized_pct,
    },
    { title: '动作', dataIndex: 'action', key: 'action', render: (v) => <Tag color="cyan">{v}</Tag> },
    { title: '说明', dataIndex: 'note', key: 'note', render: (v) => <span style={{ color: '#888' }}>{v}</span> },
    {
      title: '合约24h量',
      dataIndex: 'volume_24h',
      key: 'volume_24h',
      render: (v) => (v > 0 ? <span style={{ color: '#666' }}>{formatVolume(v)}</span> : '-'),
      sorter: (a, b) => (a.volume_24h || 0) - (b.volume_24h || 0),
    },
    {
      title: '现货24h量',
      dataIndex: 'spot_volume_24h',
      key: 'spot_volume_24h',
      render: (v) => (v > 0 ? <span style={{ color: '#666' }}>{formatVolume(v)}</span> : '-'),
      sorter: (a, b) => (a.spot_volume_24h || 0) - (b.spot_volume_24h || 0),
    },
    {
      title: '下次结算',
      dataIndex: 'next_funding_time',
      key: 'next_funding_time',
      render: (v) => formatCountdown(v),
      sorter: (a, b) => new Date(a.next_funding_time || 0) - new Date(b.next_funding_time || 0),
    },
  ];
}

export function buildLogColumns() {
  return [
    { title: '时间', dataIndex: 'timestamp', key: 'timestamp', render: (v) => fmtTime(v), width: 160 },
    {
      title: '操作',
      dataIndex: 'action',
      key: 'action',
      render: (v) => {
        const map = {
          open: ['blue', '开仓'],
          close: ['green', '平仓'],
          emergency_close: ['red', '风控平仓'],
        };
        const [color, label] = map[v] || ['default', v];
        return <Tag color={color}>{label}</Tag>;
      },
    },
    {
      title: '交易所',
      dataIndex: 'exchange',
      key: 'exchange',
      render: (v, r) => (
        <ExchangeLogoName name={v} exchangeId={r.exchange_id || r.exchange} />
      ),
    },
    { title: '交易对', dataIndex: 'symbol', key: 'symbol' },
    {
      title: '方向',
      dataIndex: 'side',
      key: 'side',
      render: (v) => <Tag color={v === 'buy' ? 'green' : 'red'}>{v === 'buy' ? '买入' : '卖出'}</Tag>,
    },
    { title: '价格', dataIndex: 'price', key: 'price', render: (v) => v?.toFixed(4) },
    { title: '备注', dataIndex: 'reason', key: 'reason', ellipsis: true },
  ];
}
