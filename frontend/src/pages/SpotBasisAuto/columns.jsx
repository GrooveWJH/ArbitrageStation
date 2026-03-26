import React from 'react';
import {
  Space,
  Tag,
  Typography,
} from 'antd';
import ExchangeLogoName from '../../components/ExchangeLogoName';
import {
  cycleModeTag,
  cycleStatusColor,
  cycleStatusLabel,
  cycleSummaryText,
  fmtPrice,
  fmtTime,
  fmtUsd,
  fmtVol,
  num,
  pctText,
} from './helpers';

export const createOpportunityColumns = () => [
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
        <Tag color="orange" className="kinetic-exchange-chip">
          <ExchangeLogoName name={r.perp_exchange_name} exchangeId={r.perp_exchange_id} />
        </Tag>
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
        <Tag color="green" className="kinetic-exchange-chip">
          <ExchangeLogoName name={r.spot_exchange_name} exchangeId={r.spot_exchange_id} />
        </Tag>
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
    render: (v) => <span style={{ color: num(v) >= 0 ? '#059669' : '#dc2626', fontWeight: 700 }}>{pctText(v, 4)}</span>,
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
    sorter: (a, b) => Math.min(num(a.perp_volume_24h, 0), num(a.spot_volume_24h, 0)) - Math.min(num(b.perp_volume_24h, 0), num(b.spot_volume_24h, 0)),
  },
];

export const createExchangeFundsColumns = () => [
  {
    title: '交易所',
    dataIndex: 'exchange_name',
    width: 120,
    render: (v, r) => (
      <Space direction="vertical" size={0}>
        <ExchangeLogoName name={v} exchangeId={r.exchange_id} />
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
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>现货 {fmtUsd(r.spot_usdt, 2)}</Typography.Text>
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>合约 {fmtUsd(r.futures_usdt, 2)}</Typography.Text>
      </Space>
    ),
  },
  {
    title: '名义占用',
    key: 'margin',
    width: 128,
    render: (_, r) => (
      <Space direction="vertical" size={0}>
        <Typography.Text style={{ fontSize: 12 }}>{fmtUsd(r.current_notional, 0)} / {fmtUsd(r.max_notional, 0)}</Typography.Text>
        <Typography.Text type="secondary" style={{ fontSize: 12 }}>利用率 {num(r.used_pct, 0).toFixed(1)}%</Typography.Text>
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

export const createCycleLogColumns = () => [
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
