import React, { useEffect, useState } from 'react';
import { Card, Table, Tag, Tooltip, Badge, Space, Button, Row, Col, Statistic, Empty } from 'antd';
import { ReloadOutlined, ThunderboltOutlined, RiseOutlined } from '@ant-design/icons';
import useNowTick from '../../hooks/useNowTick';
import { useSpreadOpportunitiesQuery } from '../../services/queries/spreadMonitorQueries';
import ExchangeLogoName from '../../components/ExchangeLogoName';

function fmtCountdown(secs) {
  if (secs == null) return '—';
  const s = Math.max(0, secs);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m ${sec}s`;
  return `${sec}s`;
}

function fmtVol(v) {
  if (!v) return '—';
  if (v >= 1e9) return `$${(v/1e9).toFixed(2)}B`;
  if (v >= 1e6) return `$${(v/1e6).toFixed(2)}M`;
  if (v >= 1e3) return `$${(v/1e3).toFixed(1)}K`;
  return `$${v.toFixed(0)}`;
}

export default function SpreadOpportunities({ wsData }) {
  const nowTick = useNowTick(1000);
  const {
    data,
    isLoading,
    isFetching,
    isFetched,
    dataUpdatedAt,
    refetch,
  } = useSpreadOpportunitiesQuery();
  const [liveOpps, setLiveOpps] = useState([]);
  const [liveUpdatedAt, setLiveUpdatedAt] = useState(null);
  const opps = liveOpps;
  const statsReady = isFetched;
  const isInitialLoading = isLoading && !isFetched;
  const isRefreshing = isFetching && !isInitialLoading;
  const lastUpdated = liveUpdatedAt || dataUpdatedAt || null;

  useEffect(() => {
    const nextOpps = Array.isArray(data?.opportunities) ? data.opportunities : [];
    setLiveOpps(nextOpps);
    if (dataUpdatedAt) {
      setLiveUpdatedAt(dataUpdatedAt);
    }
  }, [data, dataUpdatedAt]);

  useEffect(() => {
    if (wsData?.type !== 'spread_opportunities') return;
    const payload = wsData?.payload ?? wsData?.data ?? {};
    const nextOpps = Array.isArray(payload?.opportunities) ? payload.opportunities : [];
    setLiveOpps(nextOpps);

    const rawTs = wsData?.ts;
    const tsValue = typeof rawTs === 'number'
      ? rawTs
      : (rawTs ? Date.parse(String(rawTs)) : Date.now());
    setLiveUpdatedAt(Number.isFinite(tsValue) ? tsValue : Date.now());
  }, [wsData]);

  const columns = [
    {
      title: '交易对',
      dataIndex: 'symbol',
      width: 180,
      render: (sym, row) => (
        <div>
          <div style={{ fontWeight: 700, fontSize: 13 }}>{sym}</div>
          <Space size={4} style={{ marginTop: 2 }}>
            <Tag color={row.z_score >= 2 ? 'red' : 'orange'} style={{ fontSize: 10 }}>
              z={row.z_score}
            </Tag>
            <Tag color={row.funding_aligned ? 'green' : 'red'} style={{ fontSize: 10 }}>
              {row.funding_aligned ? '费率一致' : '费率反向'}
            </Tag>
          </Space>
        </div>
      ),
    },
    {
      title: '做空（高价）',
      dataIndex: 'exchange_high',
      width: 170,
      render: (ex) => (
        <div>
          <div style={{ fontWeight: 600 }}>
            <ExchangeLogoName name={ex.exchange_name} exchangeId={ex.exchange_id} />
          </div>
          <div style={{ fontSize: 11, color: '#888' }}>
            ${ex.mark_price >= 1000
              ? ex.mark_price.toLocaleString(undefined, { maximumFractionDigits: 2 })
              : ex.mark_price >= 1
              ? ex.mark_price.toFixed(4)
              : ex.mark_price.toFixed(8)}
          </div>
          <div style={{ fontSize: 11, color: ex.funding_rate_pct > 0 ? '#3f8600' : '#cf1322' }}>
            资金费 {ex.funding_rate_pct >= 0 ? '+' : ''}{ex.funding_rate_pct.toFixed(4)}%
          </div>
        </div>
      ),
    },
    {
      title: '做多（低价）',
      dataIndex: 'exchange_low',
      width: 170,
      render: (ex) => (
        <div>
          <div style={{ fontWeight: 600 }}>
            <ExchangeLogoName name={ex.exchange_name} exchangeId={ex.exchange_id} />
          </div>
          <div style={{ fontSize: 11, color: '#888' }}>
            ${ex.mark_price >= 1000
              ? ex.mark_price.toLocaleString(undefined, { maximumFractionDigits: 2 })
              : ex.mark_price >= 1
              ? ex.mark_price.toFixed(4)
              : ex.mark_price.toFixed(8)}
          </div>
          <div style={{ fontSize: 11, color: ex.funding_rate_pct > 0 ? '#3f8600' : '#cf1322' }}>
            资金费 {ex.funding_rate_pct >= 0 ? '+' : ''}{ex.funding_rate_pct.toFixed(4)}%
          </div>
        </div>
      ),
    },
    {
      title: (
        <Tooltip title="当前价差 vs 历史基线（基于3天15m数据）">
          当前 / 均值
        </Tooltip>
      ),
      width: 140,
      render: (_, row) => (
        <div>
          <div style={{ fontWeight: 700, color: '#cf1322', fontSize: 14 }}>
            {row.current_spread_pct.toFixed(4)}%
          </div>
          <div style={{ fontSize: 11, color: '#888' }}>
            均值 {row.mean_spread_pct.toFixed(4)}% · σ {row.std_spread_pct.toFixed(4)}%
          </div>
          <div style={{ fontSize: 11, color: '#fa8c16' }}>
            +1.5σ门槛 {(row.mean_spread_pct + 1.5 * row.std_spread_pct).toFixed(4)}%
          </div>
        </div>
      ),
    },
    {
      title: (
        <Tooltip title="价差回归均值后，扣除双腿往返手续费的预计净利润">
          预计净利润
        </Tooltip>
      ),
      dataIndex: 'net_profit_pct',
      width: 110,
      align: 'right',
      render: (v) => (
        <span style={{ color: v > 0 ? '#3f8600' : '#cf1322', fontWeight: 700, fontSize: 14 }}>
          {v >= 0 ? '+' : ''}{v.toFixed(4)}%
        </span>
      ),
    },
    {
      title: '手续费(往返)',
      dataIndex: 'round_trip_fee_pct',
      width: 100,
      align: 'center',
      render: (v) => <span style={{ color: '#888' }}>{v.toFixed(4)}%</span>,
    },
    {
      title: '下次结算',
      width: 120,
      render: (_, row) => {
        // secs_to_funding is recomputed server-side on every 1s poll
        const secsH = row.exchange_high.secs_to_funding;
        const secsL = row.exchange_low.secs_to_funding;
        const minSecs = Math.min(secsH ?? Infinity, secsL ?? Infinity);
        const remaining = minSecs === Infinity ? null : Math.max(0, minSecs);
        const isClose = remaining != null && remaining < 600;
        return (
          <Badge
            status={isClose ? 'processing' : 'default'}
            text={
              <span style={{ color: isClose ? '#1677ff' : undefined, fontWeight: isClose ? 600 : 400, fontSize: 12 }}>
                {remaining == null ? '—' : fmtCountdown(remaining)}
              </span>
            }
          />
        );
      },
    },
    {
      title: '24h成交量',
      dataIndex: 'min_volume_usd',
      width: 100,
      align: 'right',
      render: (v) => {
        const color = v >= 1e7 ? '#3f8600' : v >= 1e6 ? '#52c41a' : v >= 1e5 ? '#d46b08' : '#cf1322';
        return <span style={{ color, fontWeight: 600 }}>{fmtVol(v)}</span>;
      },
    },
  ];

  const staleSecs = lastUpdated ? Math.floor((nowTick - lastUpdated) / 1000) : null;

  return (
    <div>
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={6}>
          <Card size="small">
            <Statistic title="当前机会数" value={opps.length}
              valueStyle={{ color: opps.length > 0 ? '#cf1322' : '#999' }} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic title="最高z分数"
              value={opps.length > 0 ? opps[0].z_score : '—'}
              precision={opps.length > 0 ? 1 : 0}
              valueStyle={{ color: opps.length > 0 && opps[0].z_score >= 2 ? '#cf1322' : '#fa8c16' }} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic title="最大净利润"
              value={opps.length > 0 ? opps[0].net_profit_pct : '—'}
              precision={opps.length > 0 ? 4 : 0}
              suffix={opps.length > 0 ? '%' : ''}
              valueStyle={{ color: '#3f8600' }} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <div style={{ fontSize: 11, color: '#888', lineHeight: 1.6 }}>
              <div>基线：3天 × 15m K线</div>
              <div>入场条件：z ≥ 1.5 且覆盖手续费+0.1%</div>
              <div>净利润 = 价差-均值-往返手续费</div>
            </div>
          </Card>
        </Col>
      </Row>

      <Card size="small" style={{ marginBottom: 12 }} bodyStyle={{ padding: '8px 16px' }}>
        <Row align="middle" gutter={16}>
          <Col>
            <Space>
              <Badge status={statsReady ? 'success' : 'processing'} />
              <span style={{ fontSize: 12, color: '#888' }}>
                {statsReady ? '统计基线已就绪（每15分钟更新）' : '正在计算统计基线...'}
              </span>
            </Space>
          </Col>
          <Col flex="1" />
          <Col>
            <Space>
              {lastUpdated && (
                <Badge status="processing" text={
                  <span style={{ fontSize: 11, color: '#888' }}>
                    {staleSecs === 0 ? '实时' : `${staleSecs}s 前`}
                  </span>
                } />
              )}
              <Button icon={<ReloadOutlined />} size="small" onClick={() => { void refetch(); }} loading={isRefreshing}>
                刷新
              </Button>
            </Space>
          </Col>
        </Row>
      </Card>

      {!isInitialLoading && opps.length === 0 && (
        <Card>
          <Empty
            description={
              <div style={{ color: '#888' }}>
                <div>暂无满足条件的价差机会</div>
                <div style={{ fontSize: 12, marginTop: 4 }}>
                  条件：当前价差 &gt; 均值+1.5σ，且覆盖往返手续费+0.1%
                </div>
              </div>
            }
          />
        </Card>
      )}

      {opps.length > 0 && (
        <Card size="small" bodyStyle={{ padding: 0 }}>
          <Table
            rowKey="symbol"
            dataSource={opps}
            columns={columns}
            loading={isInitialLoading}
            pagination={false}
            size="small"
            scroll={{ x: 1100 }}
            rowClassName={(row) => row.funding_aligned ? 'opp-aligned' : ''}
          />
        </Card>
      )}

      <style>{`
        .opp-aligned td { background: #f6ffed !important; }
        .opp-aligned:hover td { background: #d9f7be !important; }
      `}</style>
    </div>
  );
}
