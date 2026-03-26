import React from 'react';
import { Button, Popconfirm, Space, Tag, Tooltip } from 'antd';
import { CloseCircleOutlined, EyeOutlined } from '@ant-design/icons';
import ExchangeLogoName from '../../components/ExchangeLogoName';
import { fmtTime } from '../../utils/time';
import { TermLabel } from '../../components/TermHint';

export function buildStrategyColumns({ openDetail, handleClose, statusTag, qualityTag, pnlRender }) {
  return [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 72, minWidth: 72 },
    { title: '策略', dataIndex: 'name', key: 'name', ellipsis: true, minWidth: 140 },
    {
      title: '类型',
      dataIndex: 'strategy_type',
      key: 'strategy_type',
      width: 132,
      minWidth: 132,
      render: (v) => <Tag color={v === 'cross_exchange' ? 'purple' : 'cyan'}>{v === 'cross_exchange' ? '跨所套利' : '现货对冲'}</Tag>,
    },
    { title: '交易对', dataIndex: 'symbol', key: 'symbol', minWidth: 140, render: (v) => <Tag color="blue">{v}</Tag> },
    {
      title: '做多交易所',
      dataIndex: 'long_exchange',
      key: 'long_exchange',
      width: 132,
      minWidth: 132,
      render: (v, r) => <ExchangeLogoName name={v} exchangeId={r.long_exchange_id} />,
    },
    {
      title: '做空交易所',
      dataIndex: 'short_exchange',
      key: 'short_exchange',
      width: 132,
      minWidth: 132,
      render: (v, r) => <ExchangeLogoName name={v} exchangeId={r.short_exchange_id} />,
    },
    {
      title: <TermLabel label="当前年化" term="current_annualized" />,
      dataIndex: 'current_annualized',
      key: 'current_annualized',
      width: 128,
      minWidth: 128,
      render: (v) => (v == null ? <span style={{ color: '#999' }}>--</span> : `${Number(v).toFixed(2)}%`),
      sorter: (a, b) => Number(a.current_annualized ?? -1e18) - Number(b.current_annualized ?? -1e18),
    },
    {
      title: <TermLabel label="保证金 (U)" term="capital_base" />,
      dataIndex: 'initial_margin_usd',
      key: 'initial_margin_usd',
      width: 128,
      minWidth: 128,
      render: (v) => `$${v?.toFixed(0)}`,
    },
    {
      title: <TermLabel label="价差盈亏" term="spread_pnl" />,
      dataIndex: 'unrealized_pnl',
      key: 'unrealized_pnl',
      width: 128,
      minWidth: 128,
      render: (v) => <Tooltip title="持仓期间由价格波动产生的盈亏">{pnlRender(v)}</Tooltip>,
    },
    {
      title: <TermLabel label="资金费盈亏" term="funding_pnl" />,
      dataIndex: 'funding_pnl_usd',
      key: 'funding_pnl_usd',
      width: 136,
      minWidth: 136,
      render: (v) => (v == null ? <Tag color="red">缺失</Tag> : <Tooltip title="基于资金费流水归因计算">{pnlRender(v, 4)}</Tooltip>),
    },
    {
      title: <TermLabel label="总盈亏" term="total_pnl" />,
      dataIndex: 'total_pnl_usd',
      key: 'total_pnl_usd',
      width: 146,
      minWidth: 146,
      render: (v, r) => {
        if (v == null) return <Tag color="orange">部分</Tag>;
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
      title: <TermLabel label="质量" term="quality" />,
      dataIndex: 'quality',
      key: 'quality',
      width: 96,
      minWidth: 96,
      render: (v) => qualityTag(v),
    },
    { title: '状态', dataIndex: 'status', key: 'status', minWidth: 110, render: statusTag },
    { title: '开仓时间', dataIndex: 'created_at', key: 'created_at', render: (v) => fmtTime(v), width: 168, minWidth: 168 },
    {
      title: '平仓原因',
      dataIndex: 'close_reason',
      key: 'close_reason',
      ellipsis: true,
      minWidth: 200,
      render: (v, record) =>
        v ? (
          <Tooltip title={v}>
            <span style={{ color: record.status === 'error' ? '#ff4d4f' : '#888', fontSize: 12 }}>{v}</span>
          </Tooltip>
        ) : null,
    },
    { title: '平仓时间', dataIndex: 'closed_at', key: 'closed_at', render: (v) => fmtTime(v), width: 168, minWidth: 168 },
    {
      title: '操作',
      key: 'action',
      fixed: 'right',
      width: 164,
      minWidth: 164,
      render: (_, record) => (
        <Space>
          <Button size="small" icon={<EyeOutlined />} onClick={() => openDetail(record)}>
            详情
          </Button>
          {record.status === 'active' && (
            <Popconfirm title="确认平仓？" onConfirm={() => handleClose(record.id)}>
              <Button size="small" danger icon={<CloseCircleOutlined />}>
                平仓
              </Button>
            </Popconfirm>
          )}
        </Space>
      ),
    },
  ];
}
