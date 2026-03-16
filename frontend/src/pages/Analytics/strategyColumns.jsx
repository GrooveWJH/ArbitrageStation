import React from 'react';
import { Space, Tag, Tooltip } from 'antd';
import { TermLabel } from '../../components/TermHint';
import { fmtTime } from '../../utils/time';
import { PnlText, QualityTag, StatusTag } from './renderers';

export function buildStrategyColumns() {
  return [
    { title: 'ID', dataIndex: 'strategy_id', width: 72 },
    { title: 'Type', dataIndex: 'strategy_type', width: 120 },
    { title: 'Symbol', dataIndex: 'symbol', width: 150, render: (v) => <Tag color="blue">{v}</Tag> },
    { title: 'Long', dataIndex: 'long_exchange', width: 110 },
    { title: 'Short', dataIndex: 'short_exchange', width: 110 },
    { title: <TermLabel label="Margin" term="capital_base" />, dataIndex: 'initial_margin_usd', width: 95, render: (v) => `$${Number(v || 0).toFixed(2)}` },
    {
      title: <TermLabel label="Spread" term="spread_pnl" />,
      dataIndex: 'spread_pnl_usdt',
      width: 120,
      render: (v) => <PnlText value={v} />,
      sorter: (a, b) => Number(a.spread_pnl_usdt || -1e18) - Number(b.spread_pnl_usdt || -1e18),
    },
    {
      title: <TermLabel label="Funding" term="funding_pnl" />,
      dataIndex: 'funding_pnl_usdt',
      width: 130,
      render: (v, r) => {
        if (v == null) return <Tag color="red">missing</Tag>;
        return (
          <Space size={4}>
            <PnlText value={v} />
            {r.quality !== 'ok' ? <QualityTag value={r.quality} /> : null}
          </Space>
        );
      },
    },
    {
      title: <TermLabel label="Fee" term="fee_usdt" />,
      dataIndex: 'fee_usdt',
      width: 100,
      render: (v) => <span style={{ color: '#cf1322', fontWeight: 600 }}>-{Number(v || 0).toFixed(4)} U</span>,
    },
    {
      title: <TermLabel label="Total" term="total_pnl" />,
      dataIndex: 'total_pnl_usdt',
      width: 120,
      render: (v) => {
        if (v == null) return <Tag color="orange">partial</Tag>;
        return <PnlText value={v} />;
      },
      sorter: (a, b) => Number(a.total_pnl_usdt || -1e18) - Number(b.total_pnl_usdt || -1e18),
    },
    {
      title: <TermLabel label="Quality" term="quality" />,
      dataIndex: 'quality',
      width: 90,
      render: (v) => <QualityTag value={v} />,
    },
    {
      title: <TermLabel label="Reason" term="quality_reason" />,
      dataIndex: 'quality_reason',
      width: 180,
      ellipsis: true,
      render: (v) => (v ? <Tag>{v}</Tag> : <span style={{ color: '#999' }}>-</span>),
    },
    {
      title: <TermLabel label="Funding Coverage" term="funding_coverage" />,
      key: 'coverage',
      width: 130,
      render: (_, r) => {
        const expected = Number(r.funding_expected_event_count || 0);
        const captured = Number(r.funding_captured_event_count || 0);
        if (expected <= 0) return <span style={{ color: '#999' }}>n/a</span>;
        const pct = (captured / expected) * 100;
        return (
          <Tooltip title={`${captured}/${expected}`}>
            <span>{pct.toFixed(1)}%</span>
          </Tooltip>
        );
      },
    },
    { title: 'Status', dataIndex: 'status', width: 90, render: (v) => <StatusTag value={v} /> },
    { title: 'Created', dataIndex: 'created_at', width: 160, render: (v) => fmtTime(v) },
    { title: 'Closed', dataIndex: 'closed_at', width: 160, render: (v) => fmtTime(v) },
  ];
}
