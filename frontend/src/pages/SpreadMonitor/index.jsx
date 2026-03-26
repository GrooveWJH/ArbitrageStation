import React, {
  useCallback,
  useEffect,
  useMemo,
  useState,
} from 'react';
import {
  Badge,
  Button,
  Card,
  Col,
  Input,
  InputNumber,
  Row,
  Space,
  Statistic,
  Table,
} from 'antd';
import {
  ReloadOutlined,
  SearchOutlined,
} from '@ant-design/icons';
import useNowTick from '../../hooks/useNowTick';
import api from '../../services/httpClient';
import { useSpreadMonitorGroupsQuery } from '../../services/queries/spreadMonitorQueries';
import { getApiErrorMessages } from '../../utils/error';
import { buildColumns } from './columns';
import KlineModal from './KlineModal';
import {
  composeSpreadRowClass,
  isWithinSpreadGroup,
} from './rowHover';

function computeFundingAlignment(exchanges) {
  const withPrices = exchanges.filter((e) => e.mark_price != null);
  if (withPrices.length < 2) return 'unknown';
  const sorted = [...withPrices].sort((a, b) => b.mark_price - a.mark_price);
  const highPriceEx = sorted[0];
  const lowPriceEx = sorted[sorted.length - 1];
  const diff = highPriceEx.funding_rate_pct - lowPriceEx.funding_rate_pct;
  if (diff > 0.001) return 'aligned';
  if (diff < -0.001) return 'opposed';
  return 'neutral';
}

export default function SpreadMonitor({ wsData }) {
  const nowTick = useNowTick(1000);
  const {
    data: groupsData,
    isLoading,
    isFetching,
    isFetched,
    dataUpdatedAt,
    refetch: refetchGroups,
  } = useSpreadMonitorGroupsQuery();

  const [liveGroups, setLiveGroups] = useState([]);
  const [liveUpdatedAt, setLiveUpdatedAt] = useState(null);
  const groups = liveGroups;
  const isInitialLoading = isLoading && !isFetched && groups.length === 0;
  const lastUpdated = liveUpdatedAt || dataUpdatedAt || null;

  const [search, setSearch] = useState('');
  const [minSpread, setMinSpread] = useState(0);
  const [minVolume, setMinVolume] = useState(0);
  const [sortField, setSortField] = useState('spread');
  const [sortDir, setSortDir] = useState('desc');
  const [hoveredGroupKey, setHoveredGroupKey] = useState(null);

  const [klineModal, setKlineModal] = useState(null);
  const [klineTf, setKlineTf] = useState('1h');
  const [klineData, setKlineData] = useState(null);
  const [klineLoading, setKlineLoading] = useState(false);
  const [klineError, setKlineError] = useState(null);

  useEffect(() => {
    const nextGroups = Array.isArray(groupsData?.groups) ? groupsData.groups : [];
    setLiveGroups(nextGroups);
    if (dataUpdatedAt) {
      setLiveUpdatedAt(dataUpdatedAt);
    }
  }, [groupsData, dataUpdatedAt]);

  useEffect(() => {
    if (wsData?.type !== 'spread_groups') return;
    const payload = wsData?.payload ?? wsData?.data ?? {};
    const nextGroups = Array.isArray(payload?.groups) ? payload.groups : [];
    setLiveGroups(nextGroups);

    const rawTs = wsData?.ts;
    const tsValue = typeof rawTs === 'number'
      ? rawTs
      : (rawTs ? Date.parse(String(rawTs)) : Date.now());
    setLiveUpdatedAt(Number.isFinite(tsValue) ? tsValue : Date.now());
  }, [wsData]);

  const handleSort = (field, dir) => {
    setSortField(field);
    setSortDir(dir);
  };

  const loadKline = useCallback(async (symbol, exchanges, tf) => {
    if (!symbol || exchanges.length < 2) return;
    const [exA, exB] = exchanges;
    setKlineLoading(true);
    setKlineData(null);
    setKlineError(null);
    try {
      const res = await api.get('/spread-monitor/kline', {
        params: { symbol, exchange_a: exA.id, exchange_b: exB.id, timeframe: tf, limit: 200 },
      });
      setKlineData(res.data);
    } catch (e) {
      setKlineError(getApiErrorMessages(e, '请求失败'));
    } finally {
      setKlineLoading(false);
    }
  }, []);

  const openKline = useCallback((group) => {
    const exchanges = group.exchanges;
    setKlineModal({ symbol: group.symbol, exchanges });
    setKlineTf('1h');
    setKlineError(null);
    void loadKline(group.symbol, exchanges, '1h');
  }, [loadKline]);

  const handleTfChange = (tf) => {
    setKlineTf(tf);
    if (klineModal) {
      void loadKline(klineModal.symbol, klineModal.exchanges, tf);
    }
  };

  const filtered = useMemo(() => {
    return groups
      .filter((g) => {
        if (minSpread > 0 && g.max_spread_pct < minSpread) return false;
        if (minVolume > 0 && g.min_volume_usd < minVolume) return false;
        if (search && !g.symbol.toLowerCase().includes(search.toLowerCase())) return false;
        return true;
      })
      .sort((a, b) => {
        const av = sortField === 'volume' ? a.min_volume_usd || 0 : a.max_spread_pct || 0;
        const bv = sortField === 'volume' ? b.min_volume_usd || 0 : b.max_spread_pct || 0;
        return sortDir === 'desc' ? bv - av : av - bv;
      });
  }, [groups, minSpread, minVolume, search, sortField, sortDir]);

  const rows = useMemo(() => {
    const out = [];
    filtered.forEach((g) => {
      const fundingAlignment = computeFundingAlignment(g.exchanges);
      const groupExchanges = g.exchanges.map((e) => ({ id: e.exchange_id, name: e.exchange_name }));
      g.exchanges.forEach((ex, i) => {
        out.push({
          _key: `${g.symbol}__${ex.exchange_id}`,
          _groupKey: g.symbol,
          _symbol: g.symbol,
          _maxSpreadPct: g.max_spread_pct,
          _minVolume: g.min_volume_usd,
          _exchangeCount: g.exchanges.length,
          _rowSpan: i === 0 ? g.exchanges.length : 0,
          _fundingAlignment: fundingAlignment,
          _groupExchanges: groupExchanges,
          ...ex,
        });
      });
    });
    return out;
  }, [filtered]);

  const columns = useMemo(
    () => buildColumns({ sortField, sortDir, onSort: handleSort, openKline }),
    [sortField, sortDir, openKline],
  );

  const symbolCount = filtered.length;
  const pairCount = filtered.reduce((s, g) => s + g.exchange_count, 0);
  const maxSpread = filtered.length > 0
    ? (sortField === 'spread' && sortDir === 'desc' ? filtered[0].max_spread_pct : Math.max(...filtered.map((g) => g.max_spread_pct)))
    : 0;
  const maxSpreadTone = maxSpread >= 0.1 ? 'is-alert' : 'is-watch';

  return (
    <div className="kinetic-page kinetic-spread">
      <Row gutter={16} className="kinetic-spread-metrics-row">
        <Col span={6}>
          <Card className="kinetic-panel-card" size="small">
            <Statistic title="监控币对数" value={symbolCount} />
          </Card>
        </Col>
        <Col span={6}>
          <Card className="kinetic-panel-card" size="small">
            <Statistic title="交易所数据条目" value={pairCount} />
          </Card>
        </Col>
        <Col span={6}>
          <Card className="kinetic-panel-card" size="small">
            <Statistic
              className={`kinetic-spread-stat ${maxSpreadTone}`}
              title="最大价差"
              value={maxSpread}
              precision={4}
              suffix="%"
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card className="kinetic-panel-card" size="small">
            <div className="kinetic-mini-note kinetic-spread-defs">
              <div>价差 = (该所价格 − 最低价) / 最低价</div>
              <div>高频交易所 = 组内结算最频繁的所</div>
              <div>24h成交量 = 双腿中较小值</div>
            </div>
          </Card>
        </Col>
      </Row>

      <Card className="kinetic-panel-card kinetic-spread-filter-card" size="small">
        <Row gutter={16} align="middle">
          <Col>
            <Input
              placeholder="搜索交易对"
              prefix={<SearchOutlined />}
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              allowClear
              className="kinetic-spread-search-input"
            />
          </Col>
          <Col>
            <span className="kinetic-mini-note kinetic-spread-filter-label">最小价差 ≥</span>
            <InputNumber
              value={minSpread}
              onChange={(v) => setMinSpread(v || 0)}
              min={0}
              step={0.01}
              precision={3}
              suffix="%"
              className="kinetic-spread-filter-number"
            />
          </Col>
          <Col>
            <span className="kinetic-mini-note kinetic-spread-filter-label">最小成交量 ≥</span>
            <InputNumber
              value={minVolume}
              onChange={(v) => setMinVolume(v || 0)}
              min={0}
              step={100000}
              formatter={(v) => (v ? `$${Number(v).toLocaleString()}` : '')}
              parser={(v) => (v ? Number(v.replace(/[^0-9.]/g, '')) : 0)}
              className="kinetic-spread-filter-number is-volume"
            />
          </Col>
          <Col flex="1" />
          <Col>
            <Button
              icon={<ReloadOutlined />}
              onClick={() => {
                void refetchGroups();
              }}
              loading={isFetching && !isInitialLoading}
            >
              手动刷新
            </Button>
          </Col>
          <Col>
            {(() => {
              const staleSecs = lastUpdated ? Math.floor((nowTick - lastUpdated) / 1000) : null;
              const isStale = staleSecs !== null && staleSecs > 3;
              const statusDot = !lastUpdated ? 'default' : isStale ? 'error' : 'processing';
              const label = !lastUpdated ? '加载中...' : staleSecs === 0 ? '实时' : `${staleSecs}s 前`;
              const toneClass = !lastUpdated ? 'is-idle' : isStale ? 'is-stale' : 'is-live';
              return (
                <Space size={6}>
                  <Badge status={statusDot} />
                  <span className={`kinetic-spread-tick-label ${toneClass}`}>{label}</span>
                </Space>
              );
            })()}
          </Col>
        </Row>
      </Card>

      <Card className="kinetic-panel-card kinetic-spread-table-card" size="small">
        <Table
          className="kinetic-spread-table"
          rowKey="_key"
          dataSource={rows}
          columns={columns}
          loading={isInitialLoading}
          pagination={{ pageSize: 100, showSizeChanger: true, pageSizeOptions: ['50', '100', '200'] }}
          size="small"
          scroll={{ x: 1000 }}
          rowClassName={(row) => composeSpreadRowClass(row, hoveredGroupKey)}
          onRow={(row) => ({
            'data-group-key': row._groupKey,
            onMouseEnter: () => {
              setHoveredGroupKey(row._groupKey);
            },
            onMouseLeave: (event) => {
              if (isWithinSpreadGroup(row._groupKey, event.relatedTarget)) return;
              setHoveredGroupKey((current) => (current === row._groupKey ? null : current));
            },
          })}
        />
      </Card>

      <KlineModal
        klineModal={klineModal}
        klineTf={klineTf}
        onTfChange={handleTfChange}
        klineLoading={klineLoading}
        klineError={klineError}
        klineData={klineData}
        onClose={() => {
          setKlineModal(null);
          setKlineData(null);
        }}
      />
    </div>
  );
}
