import React from 'react';
import {
  Button,
  Popconfirm,
  Tag,
  Tooltip,
} from 'antd';
import { CloseCircleOutlined } from '@ant-design/icons';
import { fmtTime } from '../../utils/time';
import { PnlCell, statusTag } from './renderers';
import { fmtPrice } from './utils';

export function buildOpenColumns({
  cfg,
  handleClose,
}) {
  return [
    {
      title: '交易对',
      dataIndex: 'symbol',
      width: 140,
      render: (sym, row) => (
        <div>
          <div style={{ fontWeight: 700 }}>{sym}</div>
          <Tag color="purple" style={{ fontSize: 10, marginTop: 2 }}>{row.order_type}</Tag>
        </div>
      ),
    },
    {
      title: '做空（高价）',
      width: 150,
      render: (_, row) => (
        <div>
          <div style={{ fontWeight: 600 }}>{row.short_exchange_name}</div>
          <div style={{ fontSize: 11, color: '#888' }}>入场 {fmtPrice(row.short_entry_price)}</div>
          <div style={{ fontSize: 11, color: '#1677ff' }}>现价 {fmtPrice(row.short_current_price)}</div>
        </div>
      ),
    },
    {
      title: '做多（低价）',
      width: 150,
      render: (_, row) => (
        <div>
          <div style={{ fontWeight: 600 }}>{row.long_exchange_name}</div>
          <div style={{ fontSize: 11, color: '#888' }}>入场 {fmtPrice(row.long_entry_price)}</div>
          <div style={{ fontSize: 11, color: '#1677ff' }}>现价 {fmtPrice(row.long_current_price)}</div>
        </div>
      ),
    },
    {
      title: '入场价差 → 当前价差',
      width: 180,
      render: (_, row) => {
        const narrowed = row.current_spread_pct < row.entry_spread_pct;
        return (
          <div>
            <div style={{ fontSize: 13 }}>
              <span style={{ color: '#888' }}>{row.entry_spread_pct?.toFixed(4)}%</span>
              <span style={{ margin: '0 6px' }}>→</span>
              <span style={{ fontWeight: 700, color: narrowed ? '#3f8600' : '#cf1322' }}>
                {row.current_spread_pct?.toFixed(4)}%
              </span>
            </div>
            <div style={{ fontSize: 11, color: '#aaa' }}>
              入场 z={row.entry_z_score?.toFixed(2)}
              {row.entry_z_score > 0 && (
                <>
                  <Tooltip title={`浮动止盈 = 入场z(${row.entry_z_score?.toFixed(2)}) - δ(${(cfg?.spread_tp_z_delta ?? 3.0).toFixed(1)})，价差收敛时提前锁利`}>
                    <span style={{ marginLeft: 6, color: '#52c41a' }}>
                      TP≤
                      {row.take_profit_z != null
                        ? row.take_profit_z.toFixed(2)
                        : (row.entry_z_score - (cfg?.spread_tp_z_delta ?? 3.0)).toFixed(2)}
                    </span>
                  </Tooltip>
                  <Tooltip title={`动态止损线 = 入场z(${row.entry_z_score?.toFixed(2)}) + δ(${(cfg?.spread_stop_z_delta ?? 1.5).toFixed(1)})`}>
                    <span style={{ marginLeft: 6, color: '#ff7875' }}>
                      SL≥
                      {(row.entry_z_score + (cfg?.spread_stop_z_delta ?? 1.5)).toFixed(1)}
                    </span>
                  </Tooltip>
                </>
              )}
            </div>
          </div>
        );
      },
    },
    {
      title: '仓位规模',
      dataIndex: 'position_size_usd',
      width: 90,
      align: 'right',
      render: (v) => <span style={{ color: '#666' }}>${v?.toFixed(2)}</span>,
    },
    {
      title: '浮动盈亏',
      dataIndex: 'unrealized_pnl_usd',
      width: 120,
      align: 'right',
      render: (v) => <PnlCell value={v} />,
      sorter: (a, b) => (a.unrealized_pnl_usd || 0) - (b.unrealized_pnl_usd || 0),
    },
    {
      title: '操作',
      width: 90,
      align: 'center',
      render: (_, row) => (
        <Popconfirm
          title="确认立即平仓？"
          description="将以市价单平掉两腿持仓"
          onConfirm={() => handleClose(row.id)}
          okText="确认平仓"
          cancelText="取消"
          okButtonProps={{ danger: true }}
        >
          <Button danger size="small" icon={<CloseCircleOutlined />}>平仓</Button>
        </Popconfirm>
      ),
    },
  ];
}

export function buildHistoryColumns() {
  return [
    { title: '交易对', dataIndex: 'symbol', width: 130, render: (s) => <Tag color="blue">{s}</Tag> },
    { title: '做空', dataIndex: 'short_exchange_name', width: 100 },
    { title: '做多', dataIndex: 'long_exchange_name', width: 100 },
    {
      title: '入场价差',
      dataIndex: 'entry_spread_pct',
      width: 100,
      render: (v) => <span style={{ color: '#cf1322' }}>{v?.toFixed(4)}%</span>,
    },
    {
      title: '入场 z',
      dataIndex: 'entry_z_score',
      width: 80,
      render: (v) => <Tag color={v >= 2 ? 'red' : 'orange'}>z={v?.toFixed(2)}</Tag>,
    },
    {
      title: '已实现盈亏',
      dataIndex: 'realized_pnl_usd',
      width: 120,
      align: 'right',
      render: (v) => <PnlCell value={v} />,
      sorter: (a, b) => (a.realized_pnl_usd || 0) - (b.realized_pnl_usd || 0),
      defaultSortOrder: 'descend',
    },
    { title: '状态', dataIndex: 'status', width: 90, render: statusTag },
    {
      title: '平仓原因',
      dataIndex: 'close_reason',
      ellipsis: true,
      render: (v) => <span style={{ fontSize: 11, color: '#888' }}>{v}</span>,
    },
    {
      title: '开仓时间',
      dataIndex: 'created_at',
      width: 140,
      render: (v) => (v ? fmtTime(v) : '—'),
    },
  ];
}
