import React from 'react';
import { Space, Tag, Tooltip } from 'antd';
import { fmtTime } from '../../utils/time';
import { TermLabel } from '../../components/TermHint';
import { formatCountdown, formatVolume } from './utils';
import { LongCell, PriceDiffCell, ShortCell } from './OpportunityCells';

export function buildOppColumns() {
  return [
    { title: '交易对', dataIndex: 'symbol', key: 'symbol', render: (v) => <Tag color="blue">{v}</Tag> },
    { title: '做多腿', key: 'long', render: (_, r) => <LongCell record={r} /> },
    { title: '做空腿', key: 'short', render: (_, r) => <ShortCell record={r} /> },
    {
      title: '费率差',
      dataIndex: 'rate_diff_pct',
      key: 'rate_diff_pct',
      render: (v) => <Tag color="green">{v.toFixed(4)}%</Tag>,
      sorter: (a, b) => b.rate_diff_pct - a.rate_diff_pct,
    },
    {
      title: <TermLabel label="年化" term="current_annualized" />,
      dataIndex: 'annualized_pct',
      key: 'annualized_pct',
      render: (v) => <span style={{ color: '#1677ff', fontWeight: 600 }}>{v.toFixed(2)}%</span>,
    },
    { title: '合约价差', key: 'price_diff_pct', render: (_, r) => <PriceDiffCell record={r} /> },
    {
      title: '最小24h量',
      dataIndex: 'min_volume_24h',
      key: 'min_volume_24h',
      render: (v) => (v > 0 ? <span style={{ color: '#888' }}>{formatVolume(v)}</span> : '-'),
      sorter: (a, b) => (b.min_volume_24h || 0) - (a.min_volume_24h || 0),
    },
  ];
}

export function buildSpotOppColumns() {
  return [
    { title: '交易对', dataIndex: 'symbol', key: 'symbol', render: (v) => <Tag color="blue">{v}</Tag> },
    {
      title: '交易所',
      key: 'exchange_name',
      render: (_, r) => (
        <Space size={4}>
          <Tag>{r.exchange_name}</Tag>
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
        <span style={{ color: v > 0 ? '#cf1322' : '#3f8600', fontWeight: 600 }}>
          {v > 0 ? '+' : ''}
          {v.toFixed(4)}%
        </span>
      ),
    },
    {
      title: <TermLabel label="年化" term="current_annualized" />,
      dataIndex: 'annualized_pct',
      key: 'annualized_pct',
      render: (v) => <span style={{ color: '#1677ff', fontWeight: 600 }}>{v.toFixed(2)}%</span>,
      sorter: (a, b) => b.annualized_pct - a.annualized_pct,
    },
    { title: '动作', dataIndex: 'action', key: 'action', render: (v) => <Tag color="cyan">{v}</Tag> },
    { title: '说明', dataIndex: 'note', key: 'note', render: (v) => <span style={{ color: '#888' }}>{v}</span> },
    {
      title: '合约24h量',
      dataIndex: 'volume_24h',
      key: 'volume_24h',
      render: (v) => (v > 0 ? <span style={{ color: '#666' }}>{formatVolume(v)}</span> : '-'),
      sorter: (a, b) => (b.volume_24h || 0) - (a.volume_24h || 0),
    },
    {
      title: '现货24h量',
      dataIndex: 'spot_volume_24h',
      key: 'spot_volume_24h',
      render: (v) => (v > 0 ? <span style={{ color: '#666' }}>{formatVolume(v)}</span> : '-'),
      sorter: (a, b) => (b.spot_volume_24h || 0) - (a.spot_volume_24h || 0),
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
    { title: '交易所', dataIndex: 'exchange', key: 'exchange' },
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
