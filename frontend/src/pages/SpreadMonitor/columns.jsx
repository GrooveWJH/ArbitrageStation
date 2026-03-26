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
import ExchangeLogoName from '../../components/ExchangeLogoName';
import SortHeader from './SortHeader';
import { fmtCountdown, fmtVolume } from './utils';

function renderMarkPrice(v) {
  if (!v) return '—';
  if (v >= 1000) return `$${v.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
  if (v >= 1) return `$${v.toFixed(4)}`;
  return `$${v.toFixed(8)}`;
}

function spreadToneClass(v) {
  if (v >= 0.1) return 'is-critical';
  if (v >= 0.02) return 'is-warning';
  return 'is-normal';
}

function volumeToneClass(v) {
  if (v >= 1e7) return 'is-xl';
  if (v >= 1e6) return 'is-high';
  if (v >= 1e5) return 'is-mid';
  return 'is-low';
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
        <div className="kinetic-spread-symbol-cell">
          <div className="kinetic-spread-symbol-main">
            <span className="kinetic-spread-symbol-text">{sym}</span>
            <Tooltip title="查看价差K线">
              <LineChartOutlined
                className="kinetic-spread-kline-trigger"
                onClick={() => openKline({ symbol: sym, exchanges: row._groupExchanges })}
              />
            </Tooltip>
          </div>
          <span className={`kinetic-spread-spread-pill ${spreadToneClass(row._maxSpreadPct)}`}>
            价差 {row._maxSpreadPct.toFixed(4)}%
          </span>
          <div className="kinetic-spread-symbol-meta">
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
        if (v === 'aligned') return <Tag className="kinetic-spread-align-tag is-aligned">一致 ✓</Tag>;
        if (v === 'opposed') return <Tag className="kinetic-spread-align-tag is-opposed">反向 ✗</Tag>;
        if (v === 'neutral') return <Tag className="kinetic-spread-align-tag is-neutral">中性</Tag>;
        return '—';
      },
    },
    {
      title: '交易所',
      dataIndex: 'exchange_name',
      width: 120,
      render: (name, row) => (
        <Space size={4} wrap>
          <ExchangeLogoName className="kinetic-spread-exchange-name" name={name} exchangeId={row.exchange_id} />
          {row.is_highest_freq && (
            <Tooltip title={`最高频率：${row.periods_per_day}次/天`}>
              <Tag className="kinetic-spread-highfreq-tag" icon={<ThunderboltOutlined />}>
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
        if (v == null) return <span className="kinetic-num kinetic-num-muted">—</span>;
        if (v === 0) return <span className="kinetic-num kinetic-num-muted">基准</span>;
        const toneClass = v >= 0.05
          ? 'kinetic-num-negative'
          : v >= 0.01
            ? 'kinetic-num-warning'
            : 'kinetic-num-strong';
        return <span className={`kinetic-num ${toneClass}`}>+{v.toFixed(4)}%</span>;
      },
    },
    {
      title: '资金费率',
      dataIndex: 'funding_rate_pct',
      width: 100,
      align: 'right',
      render: (v) => {
        if (v == null) return <span className="kinetic-num kinetic-num-muted">—</span>;
        const toneClass = v > 0.05
          ? 'kinetic-num-positive'
          : v > 0
            ? 'kinetic-num-positive'
            : v < 0
              ? 'kinetic-num-negative'
              : 'kinetic-num-muted';
        return <span className={`kinetic-num ${toneClass}`}>{v >= 0 ? '+' : ''}{v.toFixed(4)}%</span>;
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
            text={(
              <span className={`kinetic-countdown kinetic-spread-settlement ${isClose ? 'is-close' : 'is-normal'}`}>
                {fmtCountdown(remaining)}
              </span>
            )}
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
        return <Tag className={`kinetic-spread-cycle-tag ${row.is_highest_freq ? 'is-highfreq' : ''}`}>{hours}h · {ppd}次/天</Tag>;
      },
    },
    {
      title: <Tooltip title="Taker 手续费率（VIP 0 标准费率）">手续费率</Tooltip>,
      dataIndex: 'taker_fee_pct',
      width: 90,
      align: 'right',
      render: (v) => (
        <span className="kinetic-num kinetic-num-muted">
          {typeof v === 'number' ? `${v.toFixed(4)}%` : '—'}
        </span>
      ),
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
        return (
          <Tooltip title={`双腿最小成交量：${fmtVolume(vol)}`}>
            <span className={`kinetic-num kinetic-spread-volume ${volumeToneClass(vol || 0)}`}>
              {fmtVolume(vol)}
            </span>
          </Tooltip>
        );
      },
    },
  ];
}
