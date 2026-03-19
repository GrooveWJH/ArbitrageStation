import React from 'react';
import {
  Badge,
  Space,
  Tag,
  Tooltip,
} from 'antd';
import {
  LineChartOutlined,
  ThunderboltOutlined,
} from '@ant-design/icons';
import SortHeader from './SortHeader';
import { fmtCountdown, fmtVolume } from './utils';

function renderMarkPrice(v) {
  if (!v) return '—';
  if (v >= 1000) return `$${v.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
  if (v >= 1) return `$${v.toFixed(4)}`;
  return `$${v.toFixed(8)}`;
}

export function buildColumns({
  sortField,
  sortDir,
  onSort,
  openKline,
}) {
  return [
    {
      title: (
        <SortHeader
          label="交易对"
          tooltip="点击按最大价差排序"
          field="spread"
          sortField={sortField}
          sortDir={sortDir}
          onSort={onSort}
        />
      ),
      dataIndex: '_symbol',
      width: 200,
      onCell: (row) => ({ rowSpan: row._rowSpan }),
      render: (sym, row) => (
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            <span style={{ fontWeight: 600, fontSize: 13 }}>{sym}</span>
            <Tooltip title="查看价差K线">
              <LineChartOutlined
                style={{ color: '#1677ff', cursor: 'pointer', fontSize: 14 }}
                onClick={() => openKline({ symbol: sym, exchanges: row._groupExchanges })}
              />
            </Tooltip>
          </div>
          <Tag
            color={row._maxSpreadPct >= 0.1 ? 'red' : row._maxSpreadPct >= 0.02 ? 'orange' : 'default'}
            style={{ marginTop: 4, fontSize: 11 }}
          >
            价差 {row._maxSpreadPct.toFixed(4)}%
          </Tag>
          <div style={{ color: '#aaa', fontSize: 11, marginTop: 2 }}>
            {row._exchangeCount} 个交易所
          </div>
        </div>
      ),
    },
    {
      title: (
        <Tooltip title="高价所的资金费率是否也高于低价所？一致=价差由资金费驱动，收敛有动力；反向=价差来源不明，风险高">
          费率方向
        </Tooltip>
      ),
      dataIndex: '_fundingAlignment',
      width: 90,
      align: 'center',
      onCell: (row) => ({ rowSpan: row._rowSpan }),
      render: (v) => {
        if (v === 'aligned') return <Tag color="green" style={{ fontSize: 11 }}>一致 ✓</Tag>;
        if (v === 'opposed') return <Tag color="red" style={{ fontSize: 11 }}>反向 ✗</Tag>;
        if (v === 'neutral') return <Tag color="default" style={{ fontSize: 11 }}>中性</Tag>;
        return '—';
      },
    },
    {
      title: '交易所',
      dataIndex: 'exchange_name',
      width: 120,
      render: (name, row) => (
        <Space size={4} wrap>
          <span style={{ fontWeight: 500 }}>{name}</span>
          {row.is_highest_freq && (
            <Tooltip title={`最高频率：${row.periods_per_day}次/天`}>
              <Tag color="orange" icon={<ThunderboltOutlined />} style={{ fontSize: 10 }}>
                高频
              </Tag>
            </Tooltip>
          )}
        </Space>
      ),
    },
    {
      title: '标记价格',
      dataIndex: 'mark_price',
      width: 130,
      align: 'right',
      render: renderMarkPrice,
    },
    {
      title: <Tooltip title="相对本组最低价格的溢价，越高说明这个所的价格越贵">相对价差</Tooltip>,
      dataIndex: 'spread_vs_min_pct',
      width: 100,
      align: 'right',
      render: (v) => {
        if (v == null) return '—';
        const color = v === 0 ? '#999' : v >= 0.05 ? '#cf1322' : v >= 0.01 ? '#d46b08' : '#52c41a';
        return <span style={{ color, fontWeight: v > 0 ? 600 : 400 }}>{v === 0 ? '基准' : `+${v.toFixed(4)}%`}</span>;
      },
    },
    {
      title: '资金费率',
      dataIndex: 'funding_rate_pct',
      width: 100,
      align: 'right',
      render: (v) => {
        const color = v > 0.05 ? '#3f8600' : v > 0 ? '#52c41a' : v < -0.05 ? '#cf1322' : v < 0 ? '#ff7875' : '#999';
        return <span style={{ color, fontWeight: 600 }}>{v >= 0 ? '+' : ''}{v.toFixed(4)}%</span>;
      },
    },
    {
      title: '下次结算',
      dataIndex: 'secs_to_funding',
      width: 110,
      render: (secs) => {
        if (secs == null) return '—';
        const remaining = Math.max(0, secs);
        const isClose = remaining < 600;
        return (
          <Badge
            status={isClose ? 'processing' : 'default'}
            text={<span style={{ color: isClose ? '#1677ff' : undefined, fontWeight: isClose ? 600 : 400 }}>{fmtCountdown(remaining)}</span>}
          />
        );
      },
    },
    {
      title: <Tooltip title="每天结算次数；橙色 = 本组最高频率">结算周期</Tooltip>,
      dataIndex: 'periods_per_day',
      width: 100,
      align: 'center',
      render: (ppd, row) => {
        const hours = ppd > 0 ? (24 / ppd).toFixed(0) : '—';
        return <Tag color={row.is_highest_freq ? 'orange' : 'default'}>{hours}h · {ppd}次/天</Tag>;
      },
    },
    {
      title: <Tooltip title="Taker 手续费率（VIP 0 标准费率）">手续费率</Tooltip>,
      dataIndex: 'taker_fee_pct',
      width: 90,
      align: 'right',
      render: (v) => <span style={{ color: '#666' }}>{v?.toFixed(4)}%</span>,
    },
    {
      title: (
        <SortHeader
          label="24h 成交量"
          tooltip="点击按最差腿成交量排序（双腿中较小的那个）"
          field="volume"
          sortField={sortField}
          sortDir={sortDir}
          onSort={onSort}
        />
      ),
      dataIndex: 'volume_24h',
      width: 110,
      align: 'right',
      onCell: (row) => ({ rowSpan: row._rowSpan }),
      render: (_, row) => {
        const vol = row._minVolume;
        const color = vol >= 1e7 ? '#3f8600' : vol >= 1e6 ? '#52c41a' : vol >= 1e5 ? '#d46b08' : '#cf1322';
        return (
          <Tooltip title={`双腿最小成交量：${fmtVolume(vol)}`}>
            <span style={{ color, fontWeight: 600 }}>{fmtVolume(vol)}</span>
          </Tooltip>
        );
      },
    },
  ];
}
