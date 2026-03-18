import React, { useEffect, useMemo, useState } from 'react';
import {
  Row,
  Col,
  Card,
  Statistic,
  Table,
  Tag,
  Typography,
  Alert,
  Space,
  InputNumber,
  Button,
  Spin,
  Tooltip,
  Progress,
} from 'antd';
import {
  ArrowUpOutlined,
  ArrowDownOutlined,
  ThunderboltOutlined,
  ReloadOutlined,
  WalletOutlined,
} from '@ant-design/icons';
import { Line } from '@ant-design/charts';
import {
  getPnlV2Summary,
  getOpportunities,
  getSpotOpportunities,
  getTradeLogs,
  getAccountOverview,
} from '../../services/api';
import { fmtTime } from '../../utils/time';
import { TermLabel } from '../../components/TermHint';

const { Title } = Typography;

function toNumber(v) {
  const n = Number(v);
  return Number.isFinite(n) ? n : 0;
}

function calcExchangeTotalUsdt(exchangeRow) {
  if (!exchangeRow) return 0;
  const totalUsdt = toNumber(exchangeRow.total_usdt);
  if (totalUsdt > 0) return totalUsdt;
  if (exchangeRow.unified_account) return totalUsdt;
  return toNumber(exchangeRow.spot_usdt) + toNumber(exchangeRow.futures_usdt);
}

function formatUsdt(v, precision = 2) {
  return Number(v || 0).toLocaleString(undefined, {
    minimumFractionDigits: precision,
    maximumFractionDigits: precision,
  });
}
function formatCountdown(nextFundingTime) {
  if (!nextFundingTime) return '-';
  const secs = Math.floor((new Date(nextFundingTime) - Date.now()) / 1000);
  if (secs <= 0) return <Tag color="red">已结算</Tag>;

  const h = Math.floor(secs / 3600);
  const m = Math.floor((secs % 3600) / 60);
  const s = secs % 60;
  const color = secs < 600 ? '#cf1322' : secs < 1800 ? '#fa8c16' : '#888';
  const text = h > 0 ? `${h}h ${String(m).padStart(2, '0')}m` : `${m}m ${String(s).padStart(2, '0')}s`;

  return <span style={{ color, fontWeight: secs < 600 ? 600 : 400 }}>{text}</span>;
}

const _priceStore = { data: {} };
const _priceListeners = new Set();

function _updatePriceStore(data) {
  _priceStore.data = data;
  _priceListeners.forEach((fn) => fn());
}

function _usePriceDiff(symbol, longId, shortId) {
  const key = `${symbol}|${longId}|${shortId}`;
  const [data, setData] = useState(() => _priceStore.data[key] || null);

  useEffect(() => {
    const handler = () => {
      const d = _priceStore.data[key];
      if (d !== undefined) setData(d || null);
    };
    _priceListeners.add(handler);
    return () => _priceListeners.delete(handler);
  }, [key]);

  return data;
}

function periodLabel(p) {
  if (!p) return '-';
  const h = 24 / p;
  const hStr = h === Math.floor(h) ? `${h}h` : `${h.toFixed(1)}h`;
  return `每${hStr} · ${p}次/天`;
}

function LongCell({ record }) {
  const pd = _usePriceDiff(record.symbol, record.long_exchange_id, record.short_exchange_id);
  const lp = record.long_periods_per_day;
  const sp = record.short_periods_per_day;
  const isLower = lp != null && sp != null && lp < sp;

  return (
    <div style={isLower ? { background: '#fff7e6', borderRadius: 4, padding: '2px 6px' } : {}}>
      <Space size={4}>
        <Tag style={isLower ? { borderColor: '#fa8c16', color: '#fa8c16' } : {}}>{record.long_exchange}</Tag>
        <span style={{ color: record.long_rate_pct < 0 ? '#3f8600' : '#cf1322', fontSize: 12 }}>
          {record.long_rate_pct?.toFixed(4)}%
        </span>
      </Space>
      <div style={{ fontSize: 11, color: isLower ? '#fa8c16' : '#aaa', marginTop: 2 }}>
        {periodLabel(lp)} · {formatCountdown(record.long_next_funding_time)}
      </div>
      {pd?.long_price ? <div style={{ color: '#bbb', fontSize: 11 }}>${pd.long_price.toLocaleString()}</div> : null}
    </div>
  );
}

function ShortCell({ record }) {
  const pd = _usePriceDiff(record.symbol, record.long_exchange_id, record.short_exchange_id);
  const lp = record.long_periods_per_day;
  const sp = record.short_periods_per_day;
  const isLower = sp != null && lp != null && sp < lp;

  return (
    <div style={isLower ? { background: '#fff7e6', borderRadius: 4, padding: '2px 6px' } : {}}>
      <Space size={4}>
        <Tag style={isLower ? { borderColor: '#fa8c16', color: '#fa8c16' } : {}}>{record.short_exchange}</Tag>
        <span style={{ color: '#cf1322', fontSize: 12 }}>{record.short_rate_pct?.toFixed(4)}%</span>
      </Space>
      <div style={{ fontSize: 11, color: isLower ? '#fa8c16' : '#aaa', marginTop: 2 }}>
        {periodLabel(sp)} · {formatCountdown(record.short_next_funding_time)}
      </div>
      {pd?.short_price ? <div style={{ color: '#bbb', fontSize: 11 }}>${pd.short_price.toLocaleString()}</div> : null}
    </div>
  );
}

function PriceDiffCell({ record }) {
  const pd = _usePriceDiff(record.symbol, record.long_exchange_id, record.short_exchange_id);
  const value = pd?.price_diff_pct ?? record.price_diff_pct;
  if (value == null) return <span style={{ color: '#ccc' }}>-</span>;

  const color = Math.abs(value) > 0.3 ? '#cf1322' : Math.abs(value) > 0.1 ? '#fa8c16' : '#3f8600';
  return (
    <span style={{ color, fontWeight: 600 }}>
      {value > 0 ? '+' : ''}
      {value.toFixed(4)}%
    </span>
  );
}

export default function Dashboard({ wsData }) {
  const [pnlSummary, setPnlSummary] = useState({});
  const [opportunities, setOpportunities] = useState([]);
  const [spotOpportunities, setSpotOpportunities] = useState([]);
  const [logs, setLogs] = useState([]);
  const [minVolume, setMinVolume] = useState(() => Number(localStorage.getItem('dashboard_min_volume') || 0));
  const [minSpotVolume, setMinSpotVolume] = useState(() => Number(localStorage.getItem('dashboard_min_spot_volume') || 0));
  const [accountData, setAccountData] = useState([]);
  const [accountTrend, setAccountTrend] = useState([]);
  const [accountLoading, setAccountLoading] = useState(false);

  const handleMinVolumeChange = (v) => {
    const val = v || 0;
    setMinVolume(val);
    localStorage.setItem('dashboard_min_volume', val);
  };

  const handleMinSpotVolumeChange = (v) => {
    const val = v || 0;
    setMinSpotVolume(val);
    localStorage.setItem('dashboard_min_spot_volume', val);
  };

  const fetchAll = async () => {
    try {
      const [p, o, so, l] = await Promise.all([
        getPnlV2Summary(0),
        getOpportunities({ min_diff: 0.01, min_volume: minVolume }),
        getSpotOpportunities({ min_rate: 0.01, min_volume: minVolume, min_spot_volume: minSpotVolume }),
        getTradeLogs({ limit: 20 }),
      ]);
      setPnlSummary(p.data || {});
      setOpportunities(o.data);
      setSpotOpportunities(so.data);
      setLogs(l.data);
    } catch (e) {
      console.error(e);
    }
  };

  const consumeAccountOverview = (rows) => {
    const normalized = Array.isArray(rows) ? rows : [];
    setAccountData(normalized);

    const totalUsdt = normalized.reduce((sum, ex) => sum + calcExchangeTotalUsdt(ex), 0);
    const totalUnrealized = normalized.reduce(
      (sum, ex) => sum + (Array.isArray(ex.positions) ? ex.positions.reduce((s, p) => s + toNumber(p.unrealized_pnl), 0) : 0),
      0,
    );
    const now = new Date();
    const point = {
      ts: now.toISOString(),
      time: now.toLocaleTimeString([], { hour12: false }),
      total_usdt: Number(totalUsdt.toFixed(4)),
      unrealized_pnl: Number(totalUnrealized.toFixed(4)),
    };
    setAccountTrend((prev) => {
      if (prev.length === 0) return [point];
      const last = prev[prev.length - 1];
      const lastTs = new Date(last.ts).getTime();
      if (now.getTime() - lastTs < 4000) {
        return [...prev.slice(0, -1), point];
      }
      const next = [...prev, point];
      return next.slice(-180);
    });
  };

  const fetchAccount = async ({ silent = false } = {}) => {
    if (!silent) setAccountLoading(true);
    try {
      const res = await getAccountOverview();
      consumeAccountOverview(res.data || []);
    } catch (e) {
      console.error(e);
    } finally {
      if (!silent) setAccountLoading(false);
    }
  };

  useEffect(() => {
    fetchAll();
  }, [minVolume, minSpotVolume]);

  useEffect(() => {
    fetchAccount();
  }, []);

  useEffect(() => {
    const t1 = setInterval(() => {
      Promise.all([getPnlV2Summary(0)])
        .then(([p]) => {
          setPnlSummary(p.data || {});
        })
        .catch(() => {});
    }, 3000);
    const t2 = setInterval(() => {
      fetchAccount({ silent: true });
    }, 5000);
    return () => {
      clearInterval(t1);
      clearInterval(t2);
    };
  }, []);

  useEffect(() => {
    if (wsData?.type === 'price_diffs') _updatePriceStore(wsData.data);
  }, [wsData]);

  useEffect(() => {
    if (wsData?.type !== 'opportunities') return;
    const newData = wsData.data.opportunities.filter(
      (o) => !minVolume || (o.min_volume_24h || 0) >= minVolume,
    );
    setOpportunities((prev) => {
      if (prev.length === newData.length && JSON.stringify(prev) === JSON.stringify(newData)) return prev;
      return newData;
    });
  }, [wsData, minVolume]);

  const displayPnl = pnlSummary?.total_pnl_usdt;
  const pnlPct = pnlSummary?.total_pnl_pct;
  const pnlColor = displayPnl == null ? '#999' : (displayPnl >= 0 ? '#3f8600' : '#cf1322');
  const pnlIcon = displayPnl == null ? null : (displayPnl >= 0 ? <ArrowUpOutlined /> : <ArrowDownOutlined />);
  const qualityColor = {
    ok: 'green',
    na: 'blue',
    partial: 'orange',
    stale: 'volcano',
    missing: 'red',
  };
  const fundingCoveragePct = pnlSummary?.funding_coverage == null ? null : Number(pnlSummary.funding_coverage) * 100.0;
  const accountSummary = useMemo(() => {
    const out = {
      totalUsdt: 0,
      knownSpotUsdt: 0,
      knownFuturesUsdt: 0,
      altEquivalentUsdt: 0,
      unifiedUsdt: 0,
      positionCount: 0,
      unrealizedPnlUsdt: 0,
      exchangeCount: accountData.length,
      healthyExchangeCount: 0,
      warningExchangeCount: 0,
      errorExchangeCount: 0,
    };
    const mergedAssets = {};
    accountData.forEach((ex) => {
      const totalUsdt = calcExchangeTotalUsdt(ex);
      out.totalUsdt += totalUsdt;
      if (ex.unified_account) out.unifiedUsdt += toNumber(ex.total_usdt);
      else {
        const spotUsdt = toNumber(ex.spot_usdt);
        const futuresUsdt = toNumber(ex.futures_usdt);
        out.knownSpotUsdt += spotUsdt;
        out.knownFuturesUsdt += futuresUsdt;
        out.altEquivalentUsdt += Math.max(0, totalUsdt - spotUsdt - futuresUsdt);
      }

      if (ex.error) out.errorExchangeCount += 1;
      else out.healthyExchangeCount += 1;
      if (ex.warning) out.warningExchangeCount += 1;

      const positions = Array.isArray(ex.positions) ? ex.positions : [];
      out.positionCount += positions.length;
      out.unrealizedPnlUsdt += positions.reduce((s, p) => s + toNumber(p.unrealized_pnl), 0);

      const assets = Array.isArray(ex.spot_assets) ? ex.spot_assets : [];
      assets.forEach((a) => {
        if (!a?.asset) return;
        mergedAssets[a.asset] = (mergedAssets[a.asset] || 0) + toNumber(a.total);
      });
    });

    out.topAssets = Object.entries(mergedAssets)
      .map(([asset, total]) => ({ asset, total }))
      .sort((a, b) => b.total - a.total)
      .slice(0, 8);
    return out;
  }, [accountData]);

  const accountTrendStart = accountTrend.length > 0 ? toNumber(accountTrend[0].total_usdt) : null;
  const accountTrendEnd = accountTrend.length > 0 ? toNumber(accountTrend[accountTrend.length - 1].total_usdt) : null;
  const accountTrendDelta =
    accountTrendStart == null || accountTrendEnd == null ? null : accountTrendEnd - accountTrendStart;
  const accountTrendData = useMemo(
    () => accountTrend.map((p) => ({ time: p.time, total_usdt: p.total_usdt })),
    [accountTrend],
  );
  const accountTrendConfig = {
    data: accountTrendData,
    encode: { x: 'time', y: 'total_usdt' },
    smooth: true,
    animation: false,
    style: {
      stroke: '#1677ff',
      lineWidth: 2.6,
    },
    point: accountTrendData.length <= 48 ? { size: 2.5, style: { fill: '#1677ff' } } : false,
    axis: { x: { labelAutoRotate: true }, y: { labelAutoHide: true } },
  };

  const accountDistributionRows = useMemo(() => {
    return accountData
      .map((ex) => {
        const totalUsdt = calcExchangeTotalUsdt(ex);
        return {
          key: ex.exchange_id,
          name: ex.exchange_name,
          totalUsdt,
          ratio: accountSummary.totalUsdt > 0 ? (totalUsdt / accountSummary.totalUsdt) * 100 : 0,
          hasError: Boolean(ex.error),
        };
      })
      .sort((a, b) => b.totalUsdt - a.totalUsdt);
  }, [accountData, accountSummary.totalUsdt]);

  const oppColumns = [
    { title: '交易对', dataIndex: 'symbol', key: 'symbol', render: (v) => <Tag color="blue">{v}</Tag> },
    { title: '做多腿', key: 'long', render: (_, r) => <LongCell record={r} /> },
    { title: '做空腿', key: 'short', render: (_, r) => <ShortCell record={r} /> },
    {
      title: '费率差',
      dataIndex: 'rate_diff_pct',
      key: 'rate_diff_pct',
      render: (v) => <Tag color="green">{v.toFixed(4)}%</Tag>,
      sorter: (a, b) => b.rate_diff_pct - a.rate_diff_pct,
    },
    {
      title: <TermLabel label="年化" term="current_annualized" />,
      dataIndex: 'annualized_pct',
      key: 'annualized_pct',
      render: (v) => <span style={{ color: '#1677ff', fontWeight: 600 }}>{v.toFixed(2)}%</span>,
    },
    { title: '合约价差', key: 'price_diff_pct', render: (_, r) => <PriceDiffCell record={r} /> },
    {
      title: '最小24h量',
      dataIndex: 'min_volume_24h',
      key: 'min_volume_24h',
      render: (v) =>
        v > 0 ? (
          <span style={{ color: '#888' }}>
            {v >= 1e9 ? `${(v / 1e9).toFixed(1)}B` : v >= 1e6 ? `${(v / 1e6).toFixed(1)}M` : `${(v / 1e3).toFixed(0)}K`}
          </span>
        ) : (
          '-'
        ),
      sorter: (a, b) => (b.min_volume_24h || 0) - (a.min_volume_24h || 0),
    },
  ];

  const spotOppColumns = [
    { title: '交易对', dataIndex: 'symbol', key: 'symbol', render: (v) => <Tag color="blue">{v}</Tag> },
    {
      title: '交易所',
      key: 'exchange_name',
      render: (_, r) => (
        <Space size={4}>
          <Tag>{r.exchange_name}</Tag>
          {r.has_spot_market === false && (
            <Tooltip title={`${r.symbol.split(':')[0]} 在 ${r.exchange_name} 无现货交易对，无法做现货对冲`}>
              <Tag color="red">无现货</Tag>
            </Tooltip>
          )}
        </Space>
      ),
    },
    {
      title: '资金费率',
      dataIndex: 'funding_rate_pct',
      key: 'funding_rate_pct',
      render: (v) => (
        <span style={{ color: v > 0 ? '#cf1322' : '#3f8600', fontWeight: 600 }}>
          {v > 0 ? '+' : ''}
          {v.toFixed(4)}%
        </span>
      ),
    },
    {
      title: <TermLabel label="年化" term="current_annualized" />,
      dataIndex: 'annualized_pct',
      key: 'annualized_pct',
      render: (v) => <span style={{ color: '#1677ff', fontWeight: 600 }}>{v.toFixed(2)}%</span>,
      sorter: (a, b) => b.annualized_pct - a.annualized_pct,
    },
    { title: '动作', dataIndex: 'action', key: 'action', render: (v) => <Tag color="cyan">{v}</Tag> },
    { title: '说明', dataIndex: 'note', key: 'note', render: (v) => <span style={{ color: '#888' }}>{v}</span> },
    {
      title: '合约24h量',
      dataIndex: 'volume_24h',
      key: 'volume_24h',
      render: (v) =>
        v > 0 ? (
          <span style={{ color: '#666' }}>
            {v >= 1e9 ? `${(v / 1e9).toFixed(1)}B` : v >= 1e6 ? `${(v / 1e6).toFixed(1)}M` : `${(v / 1e3).toFixed(0)}K`}
          </span>
        ) : (
          '-'
        ),
      sorter: (a, b) => (b.volume_24h || 0) - (a.volume_24h || 0),
    },
    {
      title: '现货24h量',
      dataIndex: 'spot_volume_24h',
      key: 'spot_volume_24h',
      render: (v) =>
        v > 0 ? (
          <span style={{ color: '#666' }}>
            {v >= 1e9 ? `${(v / 1e9).toFixed(1)}B` : v >= 1e6 ? `${(v / 1e6).toFixed(1)}M` : `${(v / 1e3).toFixed(0)}K`}
          </span>
        ) : (
          '-'
        ),
      sorter: (a, b) => (b.spot_volume_24h || 0) - (a.spot_volume_24h || 0),
    },
    {
      title: '下次结算',
      dataIndex: 'next_funding_time',
      key: 'next_funding_time',
      render: (v) => formatCountdown(v),
      sorter: (a, b) => new Date(a.next_funding_time || 0) - new Date(b.next_funding_time || 0),
    },
  ];

  const logColumns = [
    { title: '时间', dataIndex: 'timestamp', key: 'timestamp', render: (v) => fmtTime(v), width: 160 },
    {
      title: '操作',
      dataIndex: 'action',
      key: 'action',
      render: (v) => {
        const map = {
          open: ['blue', '开仓'],
          close: ['green', '平仓'],
          emergency_close: ['red', '风控平仓'],
        };
        const [color, label] = map[v] || ['default', v];
        return <Tag color={color}>{label}</Tag>;
      },
    },
    { title: '交易所', dataIndex: 'exchange', key: 'exchange' },
    { title: '交易对', dataIndex: 'symbol', key: 'symbol' },
    {
      title: '方向',
      dataIndex: 'side',
      key: 'side',
      render: (v) => <Tag color={v === 'buy' ? 'green' : 'red'}>{v === 'buy' ? '买入' : '卖出'}</Tag>,
    },
    { title: '价格', dataIndex: 'price', key: 'price', render: (v) => v?.toFixed(4) },
    { title: '备注', dataIndex: 'reason', key: 'reason', ellipsis: true },
  ];

  const emergencyLogs = logs.filter((l) => l.action === 'emergency_close');

  return (
    <div style={{ padding: 0 }}>
      {emergencyLogs.length > 0 && (
        <Alert
          message={`有 ${emergencyLogs.length} 笔风控平仓记录`}
          description="请检查策略状态和风险规则配置"
          type="error"
          showIcon
          closable
          style={{ marginBottom: 24 }}
        />
      )}

      <Row gutter={[16, 16]} style={{ marginBottom: 24 }}>
        <Col span={4}>
          <Card>
            <Statistic title="活跃策略" value={pnlSummary.active_strategies ?? 0} prefix={<ThunderboltOutlined />} />
          </Card>
        </Col>
        <Col span={4}>
          <Card>
            <Statistic title="持仓数量" value={pnlSummary.open_positions ?? 0} />
          </Card>
        </Col>
        <Col span={5}>
          <Card>
            <Statistic
              title={<TermLabel label="策略总盈亏 (v2, USDT)" term="total_pnl" />}
              value={displayPnl == null ? '--' : Number(displayPnl)}
              precision={displayPnl == null ? undefined : 2}
              valueStyle={{ color: pnlColor }}
              prefix={pnlIcon}
            />
          </Card>
        </Col>
        <Col span={4}>
          <Card>
            <Statistic
              title={<TermLabel label="收益率 (v2)" term="total_pnl_pct" />}
              value={pnlPct == null ? '--' : Number(pnlPct)}
              precision={pnlPct == null ? undefined : 2}
              suffix="%"
              valueStyle={{ color: pnlPct == null ? '#999' : (Number(pnlPct) >= 0 ? '#3f8600' : '#cf1322') }}
            />
          </Card>
        </Col>
        <Col span={4}>
          <Card>
            <Statistic title="今日成交" value={pnlSummary.today_trades ?? 0} suffix="笔" />
          </Card>
        </Col>
        <Col span={3}>
          <Card>
            <Statistic title="在线交易所" value={pnlSummary.active_exchanges ?? 0} />
          </Card>
        </Col>
      </Row>

      <Card size="small" style={{ marginBottom: 16 }}>
        <Space wrap size={12}>
          <span style={{ color: '#666' }}>PnL口径:</span>
          <Tag color="blue">v2</Tag>
          <span style={{ color: '#666' }}>as_of:</span>
          <Tag>{fmtTime(pnlSummary?.as_of) || '-'}</Tag>
          <span style={{ color: '#666' }}><TermLabel label="quality" term="quality" />:</span>
          <Tag color={qualityColor[pnlSummary?.quality] || 'default'}>{pnlSummary?.quality || '-'}</Tag>
          <span style={{ color: '#666' }}><TermLabel label="funding_quality" term="funding_quality" />:</span>
          <Tag color={qualityColor[pnlSummary?.funding_quality] || 'default'}>{pnlSummary?.funding_quality || '-'}</Tag>
          <span style={{ color: '#666' }}><TermLabel label="funding_pnl" term="funding_pnl" />:</span>
          {pnlSummary?.funding_pnl_usdt == null ? (
            <Tag color="red">missing</Tag>
          ) : (
            <Tag color={Number(pnlSummary.funding_pnl_usdt) >= 0 ? 'green' : 'red'}>
              {Number(pnlSummary.funding_pnl_usdt).toFixed(4)}U
            </Tag>
          )}
          <span style={{ color: '#666' }}><TermLabel label="coverage" term="funding_coverage" />:</span>
          <Tag color={fundingCoveragePct == null ? 'default' : fundingCoveragePct >= 98 ? 'green' : fundingCoveragePct > 0 ? 'orange' : 'red'}>
            {fundingCoveragePct == null ? 'n/a' : `${fundingCoveragePct.toFixed(1)}%`}
          </Tag>
          <span style={{ color: '#666' }}><TermLabel label="anomaly" term="quality" />:</span>
          <Tag color={Number(pnlSummary?.anomaly_strategy_count || 0) > 0 ? 'red' : 'green'}>
            {Number(pnlSummary?.anomaly_strategy_count || 0)}
          </Tag>
        </Space>
      </Card>

      <Card
        title={<Space><WalletOutlined style={{ color: '#1677ff' }} /><span>账户资金 (实时)</span></Space>}
        style={{ marginBottom: 24 }}
        extra={
          <Button icon={<ReloadOutlined />} size="small" loading={accountLoading} onClick={fetchAccount}>
            刷新
          </Button>
        }
      >
        <Spin spinning={accountLoading}>
          {accountData.length === 0 && !accountLoading ? (
            <span style={{ color: '#aaa' }}>暂无数据，请点击刷新</span>
          ) : (
            <>
              <Row gutter={[12, 12]} style={{ marginBottom: 12 }}>
                <Col xs={24} sm={12} lg={6}>
                  <Card
                    size="small"
                    bodyStyle={{ padding: 14 }}
                    style={{ background: 'linear-gradient(135deg, #e6f4ff 0%, #f7fbff 100%)', borderColor: '#bae0ff' }}
                  >
                    <div style={{ color: '#666', fontSize: 12 }}>账户总资产 (USDT)</div>
                    <div style={{ fontSize: 24, fontWeight: 700, color: '#0958d9', lineHeight: 1.3 }}>
                      ${formatUsdt(accountSummary.totalUsdt, 2)}
                    </div>
                    <div style={{ color: '#777', fontSize: 12 }}>
                      {accountSummary.exchangeCount} 个交易所
                    </div>
                  </Card>
                </Col>
                <Col xs={24} sm={12} lg={6}>
                  <Card
                    size="small"
                    bodyStyle={{ padding: 14 }}
                    style={{ background: 'linear-gradient(135deg, #f6ffed 0%, #fcfff5 100%)', borderColor: '#d9f7be' }}
                  >
                    <div style={{ color: '#666', fontSize: 12 }}>未实现盈亏</div>
                    <div style={{ fontSize: 24, fontWeight: 700, color: accountSummary.unrealizedPnlUsdt >= 0 ? '#389e0d' : '#cf1322', lineHeight: 1.3 }}>
                      {accountSummary.unrealizedPnlUsdt >= 0 ? '+' : ''}{formatUsdt(accountSummary.unrealizedPnlUsdt, 2)}U
                    </div>
                    <div style={{ color: '#777', fontSize: 12 }}>
                      在仓头寸 {accountSummary.positionCount} 笔
                    </div>
                  </Card>
                </Col>
                <Col xs={24} sm={12} lg={6}>
                  <Card
                    size="small"
                    bodyStyle={{ padding: 14 }}
                    style={{ background: 'linear-gradient(135deg, #f0f5ff 0%, #fafcff 100%)', borderColor: '#d6e4ff' }}
                  >
                    <div style={{ color: '#666', fontSize: 12 }}>资金构成</div>
                    <div style={{ fontWeight: 600, color: '#1d39c4', marginTop: 2 }}>
                      统一账户 ${formatUsdt(accountSummary.unifiedUsdt, 2)}
                    </div>
                    <div style={{ color: '#777', fontSize: 12, marginTop: 2 }}>
                      现货 ${formatUsdt(accountSummary.knownSpotUsdt, 2)} / 合约 ${formatUsdt(accountSummary.knownFuturesUsdt, 2)}
                    </div>
                    <div style={{ color: '#777', fontSize: 12, marginTop: 2 }}>
                      山寨币折算 ${formatUsdt(accountSummary.altEquivalentUsdt, 2)}
                    </div>
                  </Card>
                </Col>
                <Col xs={24} sm={12} lg={6}>
                  <Card
                    size="small"
                    bodyStyle={{ padding: 14 }}
                    style={{ background: 'linear-gradient(135deg, #fff7e6 0%, #fffdf7 100%)', borderColor: '#ffe7ba' }}
                  >
                    <div style={{ color: '#666', fontSize: 12 }}>连接状态</div>
                    <div style={{ marginTop: 4 }}>
                      <Tag color="green" style={{ marginBottom: 4 }}>正常 {accountSummary.healthyExchangeCount}</Tag>
                      <Tag color="orange" style={{ marginBottom: 4 }}>告警 {accountSummary.warningExchangeCount}</Tag>
                      <Tag color="red" style={{ marginBottom: 4 }}>异常 {accountSummary.errorExchangeCount}</Tag>
                    </div>
                  </Card>
                </Col>
              </Row>

              <Row gutter={[16, 16]} style={{ marginBottom: 12 }}>
                <Col xs={24} xl={15}>
                  <Card
                    size="small"
                    title="资金趋势 (当前会话)"
                    extra={<Tag color="blue">{accountTrendData.length} 点</Tag>}
                    bodyStyle={{ paddingBottom: 8 }}
                  >
                    {accountTrendData.length < 2 ? (
                      <div style={{ height: 216, display: 'flex', alignItems: 'center', justifyContent: 'center', color: '#999' }}>
                        趋势数据采集中，等待更多刷新点
                      </div>
                    ) : (
                      <div style={{ height: 216 }}>
                        <Line {...accountTrendConfig} />
                      </div>
                    )}
                    <Row gutter={12} style={{ marginTop: 4, marginBottom: 2 }}>
                      <Col xs={24} sm={8}>
                        <div style={{ fontSize: 12, color: '#888' }}>起点</div>
                        <div style={{ fontWeight: 600 }}>${accountTrendStart == null ? '--' : formatUsdt(accountTrendStart, 2)}</div>
                      </Col>
                      <Col xs={24} sm={8}>
                        <div style={{ fontSize: 12, color: '#888' }}>当前</div>
                        <div style={{ fontWeight: 600 }}>${accountTrendEnd == null ? '--' : formatUsdt(accountTrendEnd, 2)}</div>
                      </Col>
                      <Col xs={24} sm={8}>
                        <div style={{ fontSize: 12, color: '#888' }}>会话变化</div>
                        <div style={{ fontWeight: 600, color: accountTrendDelta == null ? '#333' : accountTrendDelta >= 0 ? '#389e0d' : '#cf1322' }}>
                          {accountTrendDelta == null ? '--' : `${accountTrendDelta >= 0 ? '+' : ''}${formatUsdt(accountTrendDelta, 2)}U`}
                        </div>
                      </Col>
                    </Row>
                  </Card>
                </Col>
                <Col xs={24} xl={9}>
                  <Card size="small" title="交易所资产占比" bodyStyle={{ paddingBottom: 8 }}>
                    {accountDistributionRows.length === 0 ? (
                      <div style={{ color: '#999', minHeight: 216, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                        暂无可分配数据
                      </div>
                    ) : (
                      accountDistributionRows.map((row) => (
                        <div key={row.key} style={{ marginBottom: 10 }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 4 }}>
                            <div style={{ color: row.hasError ? '#cf1322' : '#333' }}>{row.name}</div>
                            <div style={{ color: '#666' }}>${formatUsdt(row.totalUsdt, 2)}</div>
                          </div>
                          <Progress
                            percent={Number(row.ratio.toFixed(1))}
                            showInfo={false}
                            size="small"
                            strokeWidth={7}
                            strokeColor={row.hasError ? '#ff7875' : '#69b1ff'}
                            trailColor="#f0f0f0"
                          />
                          <div style={{ textAlign: 'right', color: '#888', fontSize: 12 }}>{row.ratio.toFixed(1)}%</div>
                        </div>
                      ))
                    )}
                  </Card>
                </Col>
              </Row>

              {accountSummary.topAssets?.length > 0 && (
                <Card size="small" style={{ marginBottom: 12 }} title="资产分布 (按币种汇总)">
                  <Space wrap size={[6, 6]}>
                    {accountSummary.topAssets.map((a) => (
                      <Tag key={a.asset} color="blue">
                        {a.asset}: {formatUsdt(a.total, 4)}
                      </Tag>
                    ))}
                  </Space>
                </Card>
              )}

              <Row gutter={[16, 16]}>
                {accountData.map((ex) => {
                  const totalUsdt = calcExchangeTotalUsdt(ex);
                  const spotUsdt = toNumber(ex.spot_usdt);
                  const futuresUsdt = toNumber(ex.futures_usdt);
                  const altEquivalentUsdt = ex.unified_account ? 0 : Math.max(0, totalUsdt - spotUsdt - futuresUsdt);
                  const posCount = Array.isArray(ex.positions) ? ex.positions.length : 0;
                  const totalPnl = Array.isArray(ex.positions) ? ex.positions.reduce((s, p) => s + toNumber(p.unrealized_pnl), 0) : 0;
                  const spotPct = totalUsdt > 0 ? Math.min(100, (spotUsdt / totalUsdt) * 100) : 0;
                  const futuresPctRaw = totalUsdt > 0 ? (futuresUsdt / totalUsdt) * 100 : 0;
                  const futuresPct = Math.min(Math.max(0, 100 - spotPct), Math.max(0, futuresPctRaw));
                  const altPct = Math.max(0, 100 - spotPct - futuresPct);

                  return (
                    <Col key={ex.exchange_id} xs={24} sm={12} xl={8}>
                      <Card
                        size="small"
                        title={(
                          <Space size={6} wrap>
                            <Tag color="geekblue">{ex.exchange_name}</Tag>
                            {ex.unified_account && <Tag color="blue">统一账户</Tag>}
                            {ex.warning && (
                              <Tooltip title={ex.warning}>
                                <Tag color="orange">部分可用</Tag>
                              </Tooltip>
                            )}
                            {ex.error && (
                              <Tooltip title={ex.error}>
                                <Tag color="red">连接异常</Tag>
                              </Tooltip>
                            )}
                          </Space>
                        )}
                        style={{ borderColor: ex.error ? '#ffccc7' : '#e6f4ff' }}
                        bodyStyle={{ paddingTop: 10, paddingBottom: 10 }}
                      >
                        <div style={{ marginBottom: 8 }}>
                          <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 6 }}>
                            <span style={{ color: '#888', fontSize: 12 }}>总资产</span>
                            <span style={{ fontSize: 18, fontWeight: 700, color: '#0958d9' }}>${formatUsdt(totalUsdt, 2)}</span>
                          </div>
                          <div style={{ height: 8, width: '100%', background: '#f2f3f5', borderRadius: 999, overflow: 'hidden', display: 'flex' }}>
                            {ex.unified_account ? (
                              <div style={{ width: '100%', background: '#91caff' }} />
                            ) : (
                              <>
                                <div style={{ width: `${spotPct}%`, background: '#73d13d' }} />
                                <div style={{ width: `${futuresPct}%`, background: '#69b1ff' }} />
                                <div style={{ width: `${altPct}%`, background: '#95de64' }} />
                              </>
                            )}
                          </div>
                          <div style={{ marginTop: 4, display: 'flex', justifyContent: 'space-between', color: '#888', fontSize: 12 }}>
                            {ex.unified_account ? (
                              <span>统一账户余额: ${formatUsdt(ex.total_usdt || 0, 2)}</span>
                            ) : (
                              <>
                                <span>现货 ${formatUsdt(spotUsdt, 2)} ({spotPct.toFixed(1)}%)</span>
                                <span>合约 ${formatUsdt(futuresUsdt, 2)} ({futuresPct.toFixed(1)}%)</span>
                              </>
                            )}
                          </div>
                          {!ex.unified_account && (
                            <div style={{ marginTop: 2, color: '#888', fontSize: 12 }}>
                              山寨币折算 ${formatUsdt(altEquivalentUsdt, 2)} ({altPct.toFixed(1)}%)
                            </div>
                          )}
                        </div>

                        <Row gutter={8} style={{ marginBottom: 6 }}>
                          <Col span={12}>
                            <div style={{ color: '#888', fontSize: 12 }}>持仓数量</div>
                            <div style={{ fontWeight: 600 }}>{posCount} 笔</div>
                          </Col>
                          <Col span={12}>
                            <div style={{ color: '#888', fontSize: 12 }}>浮动盈亏</div>
                            <div style={{ fontWeight: 600, color: totalPnl >= 0 ? '#389e0d' : '#cf1322' }}>
                              {totalPnl >= 0 ? '+' : ''}{formatUsdt(totalPnl, 4)}U
                            </div>
                          </Col>
                        </Row>

                        {ex.spot_assets?.length > 0 && (
                          <div style={{ marginTop: 4 }}>
                            <div style={{ color: '#888', fontSize: 12, marginBottom: 3 }}>主要现货资产</div>
                            <Space size={[4, 4]} wrap>
                              {ex.spot_assets.slice(0, 6).map((a) => (
                                <Tag key={a.asset}>
                                  {a.asset}: {formatUsdt(a.total, 4)}
                                </Tag>
                              ))}
                            </Space>
                          </div>
                        )}

                        {ex.positions?.length > 0 && (
                          <div style={{ marginTop: 8 }}>
                            <div style={{ color: '#888', fontSize: 12, marginBottom: 4 }}>持仓明细</div>
                            {ex.positions.slice(0, 5).map((p, i) => (
                              <div key={`${p.symbol}-${i}`} style={{ fontSize: 12, display: 'flex', justifyContent: 'space-between', marginBottom: 3 }}>
                                <span style={{ maxWidth: '62%', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                  <Tag color={p.side === 'long' ? 'green' : 'red'} style={{ fontSize: 11, marginRight: 4 }}>
                                    {p.side}
                                  </Tag>
                                  <Tag color={(p.position_type || '').toLowerCase() === 'spot' ? 'cyan' : 'purple'} style={{ fontSize: 11, marginRight: 4 }}>
                                    {(p.position_type || 'swap').toLowerCase()}
                                  </Tag>
                                  {p.symbol}
                                </span>
                                <span style={{ color: toNumber(p.unrealized_pnl) >= 0 ? '#3f8600' : '#cf1322', fontWeight: 600 }}>
                                  {toNumber(p.unrealized_pnl) >= 0 ? '+' : ''}{formatUsdt(p.unrealized_pnl || 0, 4)}U
                                </span>
                              </div>
                            ))}
                            {ex.positions.length > 5 && (
                              <div style={{ color: '#999', fontSize: 12 }}>还有 {ex.positions.length - 5} 笔未展开</div>
                            )}
                          </div>
                        )}
                      </Card>
                    </Col>
                  );
                })}
              </Row>
            </>
          )}
        </Spin>
      </Card>

      <Card
        title={<Space><ThunderboltOutlined style={{ color: '#1677ff' }} /><span>跨所费率套利机会 (实时)</span></Space>}
        style={{ marginBottom: 24 }}
        extra={
          <Space>
            <span style={{ color: '#888', fontSize: 13 }}>最小24h量 (U):</span>
            <InputNumber
              size="small"
              min={0}
              step={1000000}
              style={{ width: 130 }}
              value={minVolume || null}
              placeholder="不限"
              formatter={(v) => (v ? `${v}`.replace(/\B(?=(\d{3})+(?!\d))/g, ',') : '')}
              onChange={handleMinVolumeChange}
            />
            <Tag color="blue">{opportunities.length} 个</Tag>
          </Space>
        }
      >
        <Table dataSource={opportunities} columns={oppColumns} rowKey="symbol" size="small" pagination={{ pageSize: 10 }} scroll={{ x: 900 }} />
      </Card>

      <Card
        title={<Space><ThunderboltOutlined style={{ color: '#13c2c2' }} /><span>现货对冲机会 (实时)</span></Space>}
        style={{ marginBottom: 24 }}
        extra={
          <Space>
            <span style={{ color: '#888', fontSize: 13 }}>合约24h量 (U):</span>
            <InputNumber
              size="small"
              min={0}
              step={1000000}
              style={{ width: 120 }}
              value={minVolume || null}
              placeholder="不限"
              formatter={(v) => (v ? `${v}`.replace(/\B(?=(\d{3})+(?!\d))/g, ',') : '')}
              onChange={handleMinVolumeChange}
            />
            <span style={{ color: '#888', fontSize: 13 }}>现货24h量 (U):</span>
            <InputNumber
              size="small"
              min={0}
              step={1000000}
              style={{ width: 120 }}
              value={minSpotVolume || null}
              placeholder="不限"
              formatter={(v) => (v ? `${v}`.replace(/\B(?=(\d{3})+(?!\d))/g, ',') : '')}
              onChange={handleMinSpotVolumeChange}
            />
            <Tag color="cyan">{spotOpportunities.length} 个</Tag>
          </Space>
        }
      >
        <Table
          dataSource={spotOpportunities}
          columns={spotOppColumns}
          rowKey={(r) => `${r.long_exchange_id ?? r.exchange_id}-${r.short_exchange_id ?? r.exchange_id}-${r.symbol}`}
          size="small"
          pagination={{ pageSize: 10 }}
          scroll={{ x: 900 }}
          rowClassName={(r) => (r.has_spot_market === false ? 'row-no-spot' : '')}
        />
      </Card>

      <Card title="最近成交记录" extra={<Tag>{logs.length} 条</Tag>}>
        <Table dataSource={logs} columns={logColumns} rowKey="id" size="small" pagination={{ pageSize: 10 }} scroll={{ x: 900 }} rowClassName={(r) => (r.action === 'emergency_close' ? 'risk-row' : '')} />
      </Card>

      <style>{`.risk-row { background: #fff1f0 !important; } .row-no-spot td { color: #bbb !important; }`}</style>
    </div>
  );
}

