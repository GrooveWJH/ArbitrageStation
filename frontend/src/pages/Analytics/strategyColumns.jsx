import React from 'react';
import { Space, Tag, Tooltip } from 'antd';
import ExchangeLogoName from '../../components/ExchangeLogoName';
import { TermLabel } from '../../components/TermHint';
import { fmtTime } from '../../utils/time';
import { PnlText, QualityTag, StatusTag } from './renderers';

export function buildStrategyColumns() {
  return [
    { title: 'ID', dataIndex: 'strategy_id', width: 72 },
    { title: '类型', dataIndex: 'strategy_type', width: 120 },
    { title: '交易对', dataIndex: 'symbol', width: 150, render: (v) => <Tag color="blue">{v}</Tag> },
    {
      title: '做多',
      dataIndex: 'long_exchange',
      width: 110,
      render: (v, r) => <ExchangeLogoName name={v} exchangeId={r.long_exchange_id} />,
    },
    {
      title: '做空',
      dataIndex: 'short_exchange',
      width: 110,
      render: (v, r) => <ExchangeLogoName name={v} exchangeId={r.short_exchange_id} />,
    },
    { title: <TermLabel label="保证金" term="capital_base" />, dataIndex: 'initial_margin_usd', width: 95, render: (v) => `$${Number(v || 0).toFixed(2)}` },
    {
      title: <TermLabel label="价差" term="spread_pnl" />,
      dataIndex: 'spread_pnl_usdt',
      width: 120,
      render: (v) => <PnlText value={v} />,
      sorter: (a, b) => Number(a.spread_pnl_usdt || -1e18) - Number(b.spread_pnl_usdt || -1e18),
    },
    {
      title: <TermLabel label="资金费" term="funding_pnl" />,
      dataIndex: 'funding_pnl_usdt',
      width: 130,
      render: (v, r) => {
        if (v == null) return <Tag color="red">缺失</Tag>;
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
      title: <TermLabel label="总计" term="total_pnl" />,
      dataIndex: 'total_pnl_usdt',
      width: 120,
      render: (v) => {
        if (v == null) return <Tag color="orange">部分</Tag>;
        return <PnlText value={v} />;
      },
      sorter: (a, b) => Number(a.total_pnl_usdt || -1e18) - Number(b.total_pnl_usdt || -1e18),
    },
    {
      title: <TermLabel label="质量" term="quality" />,
      dataIndex: 'quality',
      width: 90,
      render: (v) => <QualityTag value={v} />,
    },
    {
      title: <TermLabel label="原因" term="quality_reason" />,
      dataIndex: 'quality_reason',
      width: 180,
      ellipsis: true,
      render: (v) => (v ? <Tag>{v}</Tag> : <span style={{ color: '#999' }}>-</span>),
    },
    {
      title: <TermLabel label="资金费覆盖率" term="funding_coverage" />,
      key: 'coverage',
      width: 130,
      render: (_, r) => {
        const expected = Number(r.funding_expected_event_count || 0);
        const captured = Number(r.funding_captured_event_count || 0);
        if (expected <= 0) return <span style={{ color: '#999' }}>无</span>;
        const pct = (captured / expected) * 100;
        return (
          <Tooltip title={`${captured}/${expected}`}>
            <span>{pct.toFixed(1)}%</span>
          </Tooltip>
        );
      },
    },
    { title: '状态', dataIndex: 'status', width: 90, render: (v) => <StatusTag value={v} /> },
    { title: '创建时间', dataIndex: 'created_at', width: 160, render: (v) => fmtTime(v) },
    { title: '结束时间', dataIndex: 'closed_at', width: 160, render: (v) => fmtTime(v) },
  ];
}
