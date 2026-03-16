import React from 'react';
import { Button, Popconfirm, Space, Tag, Tooltip } from 'antd';
import { CloseCircleOutlined, EyeOutlined } from '@ant-design/icons';
import { fmtTime } from '../../utils/time';
import { TermLabel } from '../../components/TermHint';

export function buildStrategyColumns({ openDetail, handleClose, statusTag, qualityTag, pnlRender }) {
  return [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
    { title: 'Strategy', dataIndex: 'name', key: 'name', ellipsis: true },
    {
      title: 'Type',
      dataIndex: 'strategy_type',
      key: 'strategy_type',
      width: 130,
      render: (v) => <Tag color={v === 'cross_exchange' ? 'purple' : 'cyan'}>{v === 'cross_exchange' ? 'Cross Exchange' : 'Spot Hedge'}</Tag>,
    },
    { title: 'Symbol', dataIndex: 'symbol', key: 'symbol', render: (v) => <Tag color="blue">{v}</Tag> },
    { title: 'Long Ex', dataIndex: 'long_exchange', key: 'long_exchange' },
    { title: 'Short Ex', dataIndex: 'short_exchange', key: 'short_exchange' },
    {
      title: <TermLabel label="当前年化" term="current_annualized" />,
      dataIndex: 'current_annualized',
      key: 'current_annualized',
      width: 120,
      render: (v) => (v == null ? <span style={{ color: '#999' }}>--</span> : `${Number(v).toFixed(2)}%`),
      sorter: (a, b) => Number(a.current_annualized ?? -1e18) - Number(b.current_annualized ?? -1e18),
    },
    { title: <TermLabel label="Margin (U)" term="capital_base" />, dataIndex: 'initial_margin_usd', key: 'initial_margin_usd', render: (v) => `$${v?.toFixed(0)}` },
    {
      title: <TermLabel label="Spread PnL" term="spread_pnl" />,
      dataIndex: 'unrealized_pnl',
      key: 'unrealized_pnl',
      render: (v) => <Tooltip title="Price-move PnL during holding">{pnlRender(v)}</Tooltip>,
    },
    {
      title: <TermLabel label="Funding PnL" term="funding_pnl" />,
      dataIndex: 'funding_pnl_usd',
      key: 'funding_pnl_usd',
      render: (v) => (v == null ? <Tag color="red">missing</Tag> : <Tooltip title="Funding fee PnL from ledger attribution">{pnlRender(v, 4)}</Tooltip>),
    },
    {
      title: <TermLabel label="Total PnL" term="total_pnl" />,
      dataIndex: 'total_pnl_usd',
      key: 'total_pnl_usd',
      render: (v, r) => {
        if (v == null) return <Tag color="orange">partial</Tag>;
        const n = Number(v);
        const pct = r.initial_margin_usd > 0 ? (n / r.initial_margin_usd) * 100 : 0;
        return (
          <span style={{ fontWeight: 700, color: n >= 0 ? '#3f8600' : '#cf1322' }}>
            {n >= 0 ? '+' : ''}
            {n.toFixed(4)}U
            <span style={{ fontSize: 11, marginLeft: 4, color: pct >= 0 ? '#3f8600' : '#cf1322' }}>
              ({pct >= 0 ? '+' : ''}
              {pct.toFixed(2)}%)
            </span>
          </span>
        );
      },
      sorter: (a, b) => Number(a.total_pnl_usd ?? -1e18) - Number(b.total_pnl_usd ?? -1e18),
    },
    {
      title: <TermLabel label="Quality" term="quality" />,
      dataIndex: 'quality',
      key: 'quality',
      width: 92,
      render: (v) => qualityTag(v),
    },
    { title: 'Status', dataIndex: 'status', key: 'status', render: statusTag },
    { title: 'Opened At', dataIndex: 'created_at', key: 'created_at', render: (v) => fmtTime(v), width: 160 },
    {
      title: 'Close Reason',
      dataIndex: 'close_reason',
      key: 'close_reason',
      ellipsis: true,
      width: 220,
      render: (v, record) =>
        v ? (
          <Tooltip title={v}>
            <span style={{ color: record.status === 'error' ? '#ff4d4f' : '#888', fontSize: 12 }}>{v}</span>
          </Tooltip>
        ) : null,
    },
    { title: 'Closed At', dataIndex: 'closed_at', key: 'closed_at', render: (v) => fmtTime(v), width: 160 },
    {
      title: 'Action',
      key: 'action',
      fixed: 'right',
      width: 150,
      render: (_, record) => (
        <Space>
          <Button size="small" icon={<EyeOutlined />} onClick={() => openDetail(record)}>
            Detail
          </Button>
          {record.status === 'active' && (
            <Popconfirm title="Confirm close?" onConfirm={() => handleClose(record.id)}>
              <Button size="small" danger icon={<CloseCircleOutlined />}>
                Close
              </Button>
            </Popconfirm>
          )}
        </Space>
      ),
    },
  ];
}
