import React, { useEffect, useState, useRef, useCallback } from 'react';
import {
  Card, Input, Table, Tag, Tooltip, Badge, Space,
  InputNumber, Button, Row, Col, Statistic, Modal, Segmented, Spin, Empty,
} from 'antd';
import {
  ReloadOutlined, SearchOutlined, ThunderboltOutlined,
  SortAscendingOutlined, SortDescendingOutlined, LineChartOutlined,
} from '@ant-design/icons';
import axios from 'axios';

// ── Spread Candlestick Chart ───────────────────────────────────────────────────
const PAD = { left: 68, right: 16, top: 12, bottom: 52 };
const CHART_H = 300;

function niceYTicks(minV, maxV, count = 6) {
  const range = maxV - minV || 1;
  const raw = range / (count - 1);
  const mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const step = [1, 2, 2.5, 5, 10].map(f => f * mag).find(s => s >= raw) || raw;
  const lo = Math.floor(minV / step) * step;
  const ticks = [];
  for (let t = lo; t <= maxV + step * 0.01; t = Math.round((t + step) * 1e8) / 1e8) {
    ticks.push(parseFloat(t.toFixed(8)));
    if (ticks.length > count + 2) break;
  }
  return ticks.filter(t => t >= minV - step * 0.5 && t <= maxV + step * 0.5);
}

function SpreadKlineChart({ candles, timeframe, stats }) {
  const containerRef = useRef(null);
  const [width, setWidth] = useState(760);
  const [hoverIdx, setHoverIdx] = useState(null);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    setWidth(el.clientWidth);
    const ro = new ResizeObserver(() => setWidth(el.clientWidth));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);

  const cw = width - PAD.left - PAD.right;   // chart inner width
  const ch = CHART_H;

  // Y range from all OHLC values
  const allV = candles.flatMap(c => [c.open, c.high, c.low, c.close]);
  const rawMin = Math.min(...allV);
  const rawMax = Math.max(...allV);
  const pad = (rawMax - rawMin) * 0.08 || 0.5;
  const yMin = rawMin - pad;
  const yMax = rawMax + pad;
  const toY = v => PAD.top + ch * (1 - (v - yMin) / (yMax - yMin));

  // Candle geometry
  const n = candles.length;
  const slotW = cw / n;
  const bodyW = Math.max(1, Math.min(16, slotW * 0.65));
  const xOf = i => PAD.left + (i + 0.5) * slotW;

  // X labels: auto-sample
  const maxLabels = Math.max(4, Math.floor(cw / 80));
  const labelStep = Math.max(1, Math.ceil(n / maxLabels));

  // Y ticks
  const yTicks = niceYTicks(yMin, yMax, 6);

  // Time formatter for X axis
  const fmtX = (ts) => {
    const d = new Date(ts);
    if (timeframe === '1d') return `${d.getMonth()+1}/${d.getDate()}`;
    return `${String(d.getMonth()+1).padStart(2,'0')}/${String(d.getDate()).padStart(2,'0')} ${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`;
  };

  // Hover tooltip
  const svgH = PAD.top + ch + PAD.bottom;
  const handleMouseMove = (e) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const mx = e.clientX - rect.left - PAD.left;
    const idx = Math.round(mx / slotW - 0.5);
    setHoverIdx(idx >= 0 && idx < n ? idx : null);
  };

  const hov = hoverIdx != null ? candles[hoverIdx] : null;

  return (
    <div ref={containerRef} style={{ width: '100%', userSelect: 'none' }}>
      <svg
        width={width}
        height={svgH}
        onMouseMove={handleMouseMove}
        onMouseLeave={() => setHoverIdx(null)}
        style={{ display: 'block' }}
      >
        {/* Y grid + labels */}
        {yTicks.map((t, i) => {
          const y = toY(t);
          const isZero = Math.abs(t) < 0.0001;
          return (
            <g key={i}>
              <line
                x1={PAD.left} x2={PAD.left + cw} y1={y} y2={y}
                stroke={isZero ? '#aaa' : '#f0f0f0'}
                strokeWidth={isZero ? 1.5 : 1}
                strokeDasharray={isZero ? '5,4' : undefined}
              />
              <text x={PAD.left - 6} y={y + 4} textAnchor="end" fontSize={10} fill={isZero ? '#666' : '#aaa'}>
                {t.toFixed(Math.abs(t) < 1 ? 3 : 2)}%
              </text>
            </g>
          );
        })}

        {/* Candles */}
        {candles.map((c, i) => {
          const x = xOf(i);
          const isUp = c.close >= c.open;
          const color = isUp ? '#ef5350' : '#26a69a'; // red=widened, green=narrowed
          const bodyTop = toY(Math.max(c.open, c.close));
          const bodyBot = toY(Math.min(c.open, c.close));
          const bodyH = Math.max(1.5, bodyBot - bodyTop);
          const isHov = hoverIdx === i;
          return (
            <g key={i} opacity={hoverIdx != null && !isHov ? 0.5 : 1}>
              {/* Hover highlight */}
              {isHov && (
                <rect
                  x={x - slotW / 2} y={PAD.top} width={slotW} height={ch}
                  fill="#f5f5f5" opacity={0.5}
                />
              )}
              {/* Wick */}
              <line x1={x} x2={x} y1={toY(c.high)} y2={toY(c.low)} stroke={color} strokeWidth={1.2} />
              {/* Body */}
              <rect
                x={x - bodyW / 2} y={bodyTop} width={bodyW} height={bodyH}
                fill={color} stroke={color} strokeWidth={0.5}
              />
            </g>
          );
        })}

        {/* Hover vertical line */}
        {hov && (
          <line
            x1={xOf(hoverIdx)} x2={xOf(hoverIdx)}
            y1={PAD.top} y2={PAD.top + ch}
            stroke="#999" strokeWidth={1} strokeDasharray="3,3"
          />
        )}

        {/* Stats reference lines */}
        {stats && (() => {
          const lines = [
            { value: stats.mean, color: '#1677ff', dash: '6,3', label: `均值 ${stats.mean >= 0 ? '+' : ''}${stats.mean.toFixed(4)}%` },
            { value: stats.upper_1_5, color: '#fa8c16', dash: '4,3', label: `+1.5σ ${stats.upper_1_5.toFixed(4)}%` },
            { value: stats.upper_2, color: '#cf1322', dash: '3,3', label: `+2σ ${stats.upper_2.toFixed(4)}%` },
          ];
          return lines.map(({ value, color, dash, label }) => {
            if (value < yMin || value > yMax) return null;
            const y = toY(value);
            return (
              <g key={label}>
                <line x1={0} x2={cw} y1={y} y2={y} stroke={color} strokeWidth={1.2} strokeDasharray={dash} opacity={0.8} transform={`translate(${PAD.left}, 0)`} />
                <text x={PAD.left + cw - 4} y={y - 3} textAnchor="end" fontSize={9} fill={color} opacity={0.9}>{label}</text>
              </g>
            );
          });
        })()}

        {/* X axis labels */}
        {candles.map((c, i) => {
          if (i % labelStep !== 0) return null;
          const x = xOf(i);
          return (
            <text
              key={i} x={x} y={PAD.top + ch + 18}
              textAnchor="middle" fontSize={10} fill="#aaa"
              transform={`rotate(-35, ${x}, ${PAD.top + ch + 18})`}
            >
              {fmtX(c.time)}
            </text>
          );
        })}

        {/* Tooltip box */}
        {hov && (() => {
          const x = xOf(hoverIdx);
          const isUp = hov.close >= hov.open;
          const color = isUp ? '#ef5350' : '#26a69a';
          const lines = [
            fmtX(hov.time),
            `开 ${hov.open >= 0 ? '+' : ''}${hov.open.toFixed(4)}%`,
            `高 ${hov.high >= 0 ? '+' : ''}${hov.high.toFixed(4)}%`,
            `低 ${hov.low >= 0 ? '+' : ''}${hov.low.toFixed(4)}%`,
            `收 ${hov.close >= 0 ? '+' : ''}${hov.close.toFixed(4)}%`,
          ];
          const bw = 130, bh = lines.length * 16 + 10;
          const bx = x + 12 + bw > PAD.left + cw ? x - bw - 12 : x + 12;
          const by = Math.max(PAD.top, Math.min(PAD.top + ch - bh, toY(hov.high) - 10));
          return (
            <g>
              <rect x={bx} y={by} width={bw} height={bh} rx={4}
                fill="white" stroke="#e0e0e0" strokeWidth={1} filter="url(#shadow)" />
              {lines.map((l, li) => (
                <text key={li} x={bx + 8} y={by + 14 + li * 16}
                  fontSize={11} fill={li === 0 ? '#666' : (li === 4 ? color : '#333')}
                  fontWeight={li === 4 ? 600 : 400}>
                  {l}
                </text>
              ))}
            </g>
          );
        })()}

        <defs>
          <filter id="shadow" x="-10%" y="-10%" width="120%" height="120%">
            <feDropShadow dx="0" dy="1" stdDeviation="2" floodColor="#00000022" />
          </filter>
        </defs>
      </svg>
    </div>
  );
}

const api = axios.create({ baseURL: '/api' });

// ── Countdown helper ──────────────────────────────────────────────────────────
function useCountdowns() {
  const [tick, setTick] = useState(0);
  useEffect(() => {
    const t = setInterval(() => setTick(n => n + 1), 1000);
    return () => clearInterval(t);
  }, []);
  return tick;
}

function fmtCountdown(secsToFunding) {
  if (secsToFunding == null) return '—';
  const s = Math.max(0, secsToFunding);
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m ${sec}s`;
  return `${sec}s`;
}

function fmtVolume(v) {
  if (!v || v <= 0) return '—';
  if (v >= 1e9) return `$${(v / 1e9).toFixed(2)}B`;
  if (v >= 1e6) return `$${(v / 1e6).toFixed(2)}M`;
  if (v >= 1e3) return `$${(v / 1e3).toFixed(1)}K`;
  return `$${v.toFixed(0)}`;
}

// ── Sort header component ─────────────────────────────────────────────────────
function SortHeader({ label, tooltip, field, sortField, sortDir, onSort }) {
  const active = sortField === field;
  const Icon = active && sortDir === 'asc' ? SortAscendingOutlined : SortDescendingOutlined;
  return (
    <Tooltip title={tooltip}>
      <span
        style={{ cursor: 'pointer', userSelect: 'none' }}
        onClick={() => {
          if (active) {
            onSort(field, sortDir === 'desc' ? 'asc' : 'desc');
          } else {
            onSort(field, 'desc');
          }
        }}
      >
        {label}{' '}
        <Icon style={{ color: active ? '#1677ff' : '#bbb', fontSize: 13 }} />
      </span>
    </Tooltip>
  );
}

// ── Main component ────────────────────────────────────────────────────────────
export default function SpreadMonitor({ wsData }) {
  const [groups, setGroups] = useState([]);
  const [loading, setLoading] = useState(false);
  const [lastUpdated, setLastUpdated] = useState(null); // ms epoch
  const [nowTick, setNowTick] = useState(Date.now());

  // Live clock for staleness display
  useEffect(() => {
    const t = setInterval(() => setNowTick(Date.now()), 1000);
    return () => clearInterval(t);
  }, []);

  const [search, setSearch] = useState('');
  const [minSpread, setMinSpread] = useState(0);
  const [minVolume, setMinVolume] = useState(0);
  const [sortField, setSortField] = useState('spread');
  const [sortDir, setSortDir] = useState('desc');
  // ── Kline modal state ──────────────────────────────────────────────────────
  const [klineModal, setKlineModal] = useState(null);
  const [klineTf, setKlineTf] = useState('1h');
  const [klineData, setKlineData] = useState(null);
  const [klineLoading, setKlineLoading] = useState(false);
  const [klineError, setKlineError] = useState(null);

  const fetchedAt = useRef(null);
  const isFetching = useRef(false); // prevent concurrent requests
  useCountdowns();

  // ── Initial load (with spinner) ───────────────────────────────────────────
  const load = useCallback(async (silent = false) => {
    if (isFetching.current) return; // skip if previous request still in flight
    isFetching.current = true;
    if (!silent) setLoading(true);
    try {
      const res = await api.get('/spread-monitor/groups');
      setGroups(res.data.groups || []);
      fetchedAt.current = Date.now();
      setLastUpdated(Date.now());
    } catch (e) {
      console.error(e);
    } finally {
      isFetching.current = false;
      if (!silent) setLoading(false);
    }
  }, []);

  // Initial load with spinner
  useEffect(() => { load(false); }, [load]);

  // 1s polling — silent (no spinner, no flicker) while page is active
  useEffect(() => {
    const t = setInterval(() => load(true), 1000);
    return () => clearInterval(t);
  }, [load]);

  const handleSort = (field, dir) => {
    setSortField(field);
    setSortDir(dir);
  };

  // ── Kline fetch ────────────────────────────────────────────────────────────
  const loadKline = useCallback(async (symbol, exchanges, tf) => {
    if (!symbol || exchanges.length < 2) return;
    // Use highest-price exchange as A, lowest as B (consistent with spread direction)
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
      const detail = e?.response?.data?.detail;
      const msgs = detail?.errors || [detail?.message || e.message || '请求失败'];
      setKlineError(msgs);
    } finally {
      setKlineLoading(false);
    }
  }, []);

  const openKline = useCallback((group) => {
    const exchanges = group.exchanges; // already [{id, name}] from _groupExchanges
    setKlineModal({ symbol: group.symbol, exchanges });
    setKlineTf('1h');
    setKlineError(null);
    loadKline(group.symbol, exchanges, '1h');
  }, [loadKline]);

  const handleTfChange = (tf) => {
    setKlineTf(tf);
    if (klineModal) loadKline(klineModal.symbol, klineModal.exchanges, tf);
  };

  // ── Filter & sort (group level) ────────────────────────────────────────────
  const filtered = groups
    .filter(g => {
      if (minSpread > 0 && g.max_spread_pct < minSpread) return false;
      if (minVolume > 0 && g.min_volume_usd < minVolume) return false;
      if (search && !g.symbol.toLowerCase().includes(search.toLowerCase())) return false;
      return true;
    })
    .sort((a, b) => {
      let av, bv;
      if (sortField === 'volume') {
        av = a.min_volume_usd || 0;
        bv = b.min_volume_usd || 0;
      } else {
        av = a.max_spread_pct || 0;
        bv = b.max_spread_pct || 0;
      }
      return sortDir === 'desc' ? bv - av : av - bv;
    });

  // ── Flatten for Table (rowSpan on symbol column) ───────────────────────────
  const rows = [];
  filtered.forEach(g => {
    // Compute funding alignment for group:
    // Compare the funding rate of the highest-price exchange vs lowest-price exchange.
    // "一致" = higher price also has higher funding rate (funding drives the spread → convergence expected)
    // "反向" = higher price has lower funding rate (structural dislocation, risky)
    let fundingAlignment = 'unknown';
    const withPrices = g.exchanges.filter(e => e.mark_price != null);
    if (withPrices.length >= 2) {
      const sorted = [...withPrices].sort((a, b) => b.mark_price - a.mark_price);
      const highPriceEx = sorted[0];
      const lowPriceEx = sorted[sorted.length - 1];
      const diff = highPriceEx.funding_rate_pct - lowPriceEx.funding_rate_pct;
      if (diff > 0.001) fundingAlignment = 'aligned';       // 高价所费率也高 → 一致
      else if (diff < -0.001) fundingAlignment = 'opposed'; // 高价所费率反而低 → 反向
      else fundingAlignment = 'neutral';                     // 差异极小
    }

    // Pre-build exchange list for kline (highest price first = same order as entries)
    const groupExchanges = g.exchanges.map(e => ({ id: e.exchange_id, name: e.exchange_name }));

    g.exchanges.forEach((ex, i) => {
      rows.push({
        _key: `${g.symbol}__${ex.exchange_id}`,
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

  // ── Columns ────────────────────────────────────────────────────────────────
  const columns = [
    {
      title: (
        <SortHeader
          label="交易对"
          tooltip="点击按最大价差排序"
          field="spread"
          sortField={sortField}
          sortDir={sortDir}
          onSort={handleSort}
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
        if (v === 'aligned')  return <Tag color="green"  style={{ fontSize: 11 }}>一致 ✓</Tag>;
        if (v === 'opposed')  return <Tag color="red"    style={{ fontSize: 11 }}>反向 ✗</Tag>;
        if (v === 'neutral')  return <Tag color="default" style={{ fontSize: 11 }}>中性</Tag>;
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
      render: (v) => {
        if (!v) return '—';
        if (v >= 1000) return `$${v.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
        if (v >= 1) return `$${v.toFixed(4)}`;
        return `$${v.toFixed(8)}`;
      },
    },
    {
      title: (
        <Tooltip title="相对本组最低价格的溢价，越高说明这个所的价格越贵">
          相对价差
        </Tooltip>
      ),
      dataIndex: 'spread_vs_min_pct',
      width: 100,
      align: 'right',
      render: (v) => {
        if (v == null) return '—';
        const color = v === 0 ? '#999' : v >= 0.05 ? '#cf1322' : v >= 0.01 ? '#d46b08' : '#52c41a';
        return (
          <span style={{ color, fontWeight: v > 0 ? 600 : 400 }}>
            {v === 0 ? '基准' : `+${v.toFixed(4)}%`}
          </span>
        );
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
        // secs_to_funding is recomputed server-side on every 1s poll, use directly
        const remaining = Math.max(0, secs);
        const isClose = remaining < 600;
        return (
          <Badge
            status={isClose ? 'processing' : 'default'}
            text={
              <span style={{ color: isClose ? '#1677ff' : undefined, fontWeight: isClose ? 600 : 400 }}>
                {fmtCountdown(remaining)}
              </span>
            }
          />
        );
      },
    },
    {
      title: (
        <Tooltip title="每天结算次数；橙色 = 本组最高频率">
          结算周期
        </Tooltip>
      ),
      dataIndex: 'periods_per_day',
      width: 100,
      align: 'center',
      render: (ppd, row) => {
        const hours = ppd > 0 ? (24 / ppd).toFixed(0) : '—';
        return (
          <Tag color={row.is_highest_freq ? 'orange' : 'default'}>
            {hours}h · {ppd}次/天
          </Tag>
        );
      },
    },
    {
      title: (
        <Tooltip title="Taker 手续费率（VIP 0 标准费率）">
          手续费率
        </Tooltip>
      ),
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
          onSort={handleSort}
        />
      ),
      dataIndex: 'volume_24h',
      width: 110,
      align: 'right',
      onCell: (row) => ({ rowSpan: row._rowSpan }),
      render: (v, row) => {
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

  const symbolCount = filtered.length;
  const pairCount = filtered.reduce((s, g) => s + g.exchange_count, 0);
  const maxSpread = filtered.length > 0
    ? (sortField === 'spread' && sortDir === 'desc' ? filtered[0].max_spread_pct : Math.max(...filtered.map(g => g.max_spread_pct)))
    : 0;

  return (
    <div>
      {/* ── 统计行 ──────────────────────────────────────────────────────────── */}
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={6}>
          <Card size="small">
            <Statistic title="监控币对数" value={symbolCount} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic title="交易所数据条目" value={pairCount} />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <Statistic
              title="最大价差"
              value={maxSpread}
              precision={4}
              suffix="%"
              valueStyle={{ color: maxSpread >= 0.1 ? '#cf1322' : '#d46b08' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card size="small">
            <div style={{ color: '#888', fontSize: 12 }}>
              <div>价差 = (该所价格 − 最低价) / 最低价</div>
              <div>高频交易所 = 组内结算最频繁的所</div>
              <div>24h成交量 = 双腿中较小值</div>
            </div>
          </Card>
        </Col>
      </Row>

      {/* ── 过滤栏 ─────────────────────────────────────────────────────────── */}
      <Card
        size="small"
        style={{ marginBottom: 16 }}
        bodyStyle={{ padding: '8px 16px' }}
      >
        <Row gutter={16} align="middle">
          <Col>
            <Input
              placeholder="搜索交易对"
              prefix={<SearchOutlined />}
              value={search}
              onChange={e => setSearch(e.target.value)}
              allowClear
              style={{ width: 200 }}
            />
          </Col>
          <Col>
            <span style={{ color: '#888', marginRight: 8 }}>最小价差 ≥</span>
            <InputNumber
              value={minSpread}
              onChange={v => setMinSpread(v || 0)}
              min={0}
              step={0.01}
              precision={3}
              suffix="%"
              style={{ width: 100 }}
            />
          </Col>
          <Col>
            <span style={{ color: '#888', marginRight: 8 }}>最小成交量 ≥</span>
            <InputNumber
              value={minVolume}
              onChange={v => setMinVolume(v || 0)}
              min={0}
              step={100000}
              formatter={v => v ? `$${Number(v).toLocaleString()}` : ''}
              parser={v => v ? Number(v.replace(/[^0-9.]/g, '')) : 0}
              style={{ width: 130 }}
            />
          </Col>
          <Col flex="1" />
          <Col>
            <Button icon={<ReloadOutlined />} onClick={load} loading={loading}>
              手动刷新
            </Button>
          </Col>
          <Col>
            {(() => {
              const staleSecs = lastUpdated ? Math.floor((nowTick - lastUpdated) / 1000) : null;
              const isStale = staleSecs !== null && staleSecs > 3;
              const color = !lastUpdated ? '#aaa' : isStale ? '#cf1322' : '#52c41a';
              const statusDot = !lastUpdated ? 'default' : isStale ? 'error' : 'processing';
              const label = !lastUpdated
                ? '加载中...'
                : staleSecs === 0
                  ? '实时'
                  : `${staleSecs}s 前`;
              return (
                <Space size={6}>
                  <Badge status={statusDot} />
                  <span style={{ color, fontSize: 12 }}>{label}</span>
                </Space>
              );
            })()}
          </Col>
        </Row>
      </Card>

      {/* ── 主表格 ─────────────────────────────────────────────────────────── */}
      <Card size="small" bodyStyle={{ padding: 0 }}>
        <Table
          rowKey="_key"
          dataSource={rows}
          columns={columns}
          loading={loading}
          pagination={{ pageSize: 100, showSizeChanger: true, pageSizeOptions: ['50', '100', '200'] }}
          size="small"
          scroll={{ x: 1000 }}
          rowClassName={(row) => row.is_highest_freq ? 'row-highest-freq' : ''}
        />
      </Card>

      <style>{`
        .row-highest-freq td { background: #fff7e6 !important; }
        .row-highest-freq:hover td { background: #fef3d0 !important; }
      `}</style>

      {/* ── 价差K线 Modal ────────────────────────────────────────────────────── */}
      <Modal
        open={!!klineModal}
        onCancel={() => { setKlineModal(null); setKlineData(null); }}
        footer={null}
        width={1000}
        title={
          klineModal && (
            <Space>
              <LineChartOutlined />
              <span>{klineModal.symbol} 价差走势</span>
              {klineData && (
                <span style={{ fontWeight: 400, color: '#888', fontSize: 13 }}>
                  {klineData.exchange_a} − {klineData.exchange_b}
                </span>
              )}
              {klineData?.stats && (() => {
                const latest = klineData.candles[klineData.candles.length - 1]?.close;
                const z = latest && klineData.stats.std > 0
                  ? ((latest - klineData.stats.mean) / klineData.stats.std).toFixed(1)
                  : null;
                if (!z) return null;
                const color = z >= 1.5 ? '#cf1322' : z >= 1 ? '#fa8c16' : '#52c41a';
                return <Tag color={z >= 1.5 ? 'red' : z >= 1 ? 'orange' : 'green'} style={{ marginLeft: 8 }}>z={z}</Tag>;
              })()}
            </Space>
          )
        }
        destroyOnClose
      >
        <div style={{ marginBottom: 12 }}>
          <Segmented
            value={klineTf}
            onChange={handleTfChange}
            options={[
              { label: '15m', value: '15m' },
              { label: '1h',  value: '1h'  },
              { label: '4h',  value: '4h'  },
              { label: '1d',  value: '1d'  },
            ]}
          />
        </div>

        {klineLoading && (
          <div style={{ textAlign: 'center', padding: '60px 0' }}>
            <Spin size="large" />
          </div>
        )}

        {!klineLoading && klineError && (
          <Empty
            description={
              <div style={{ textAlign: 'left', color: '#cf1322' }}>
                {klineError.map((msg, i) => <div key={i}>• {msg}</div>)}
              </div>
            }
          />
        )}

        {!klineLoading && klineData && klineData.candles.length > 0 && (() => {
          const cs = klineData.candles;
          const latest = cs[cs.length - 1].close;
          const closes = cs.map(c => c.close);
          const highs  = cs.map(c => c.high);
          const lows   = cs.map(c => c.low);
          const maxS = Math.max(...highs);
          const minS = Math.min(...lows);
          const avg  = closes.reduce((a, b) => a + b, 0) / closes.length;

          const st = klineData.stats;
          const currentZ = st && st.std > 0 ? (latest - st.mean) / st.std : null;

          return (
            <>
              <Row gutter={8} style={{ marginBottom: 8 }}>
                {[
                  { label: '最新价差', value: latest, color: latest >= 0 ? '#ef5350' : '#26a69a' },
                  { label: '均值',     value: avg,    color: avg >= 0 ? '#ef5350' : '#26a69a' },
                  { label: '区间最高', value: maxS,   color: '#ef5350' },
                  { label: '区间最低', value: minS,   color: '#26a69a' },
                ].map(({ label, value, color }) => (
                  <Col span={6} key={label}>
                    <Card size="small" bodyStyle={{ padding: '6px 10px' }}>
                      <div style={{ fontSize: 10, color: '#aaa' }}>{label}</div>
                      <div style={{ fontWeight: 700, fontSize: 14, color }}>
                        {value >= 0 ? '+' : ''}{value.toFixed(4)}%
                      </div>
                    </Card>
                  </Col>
                ))}
              </Row>

              {st && (
                <Row gutter={8} style={{ marginBottom: 8 }}>
                  <Col span={6}>
                    <Card size="small" bodyStyle={{ padding: '6px 10px' }}>
                      <div style={{ fontSize: 10, color: '#aaa' }}>历史均值</div>
                      <div style={{ fontWeight: 700, fontSize: 14, color: '#1677ff' }}>
                        {st.mean >= 0 ? '+' : ''}{st.mean.toFixed(4)}%
                      </div>
                    </Card>
                  </Col>
                  <Col span={6}>
                    <Card size="small" bodyStyle={{ padding: '6px 10px' }}>
                      <div style={{ fontSize: 10, color: '#aaa' }}>+1.5σ门槛</div>
                      <div style={{ fontWeight: 700, fontSize: 14, color: '#fa8c16' }}>
                        {st.upper_1_5 >= 0 ? '+' : ''}{st.upper_1_5.toFixed(4)}%
                      </div>
                    </Card>
                  </Col>
                  <Col span={6}>
                    <Card size="small" bodyStyle={{ padding: '6px 10px' }}>
                      <div style={{ fontSize: 10, color: '#aaa' }}>当前z分数</div>
                      <div style={{
                        fontWeight: 700, fontSize: 14,
                        color: currentZ >= 1.5 ? '#cf1322' : currentZ >= 1 ? '#fa8c16' : '#52c41a',
                      }}>
                        {currentZ != null ? currentZ.toFixed(2) : '—'}
                      </div>
                    </Card>
                  </Col>
                  <Col span={6}>
                    <Card size="small" bodyStyle={{ padding: '6px 10px' }}>
                      <div style={{ fontSize: 10, color: '#aaa' }}>数据样本</div>
                      <div style={{ fontWeight: 700, fontSize: 14, color: '#666' }}>
                        {st.n} 根
                      </div>
                    </Card>
                  </Col>
                </Row>
              )}

              <div style={{ fontSize: 11, color: '#aaa', marginBottom: 6, display: 'flex', gap: 16 }}>
                <span><span style={{ display: 'inline-block', width: 10, height: 10, background: '#ef5350', marginRight: 4 }} />价差扩大</span>
                <span><span style={{ display: 'inline-block', width: 10, height: 10, background: '#26a69a', marginRight: 4 }} />价差收窄</span>
                {st && (
                  <>
                    <span><span style={{ display: 'inline-block', width: 16, height: 2, background: '#1677ff', marginRight: 4, verticalAlign: 'middle' }} />均值</span>
                    <span><span style={{ display: 'inline-block', width: 16, height: 2, background: '#fa8c16', marginRight: 4, verticalAlign: 'middle' }} />+1.5σ</span>
                    <span><span style={{ display: 'inline-block', width: 16, height: 2, background: '#cf1322', marginRight: 4, verticalAlign: 'middle' }} />+2σ</span>
                  </>
                )}
                <span style={{ marginLeft: 'auto' }}>{cs.length} 根K线</span>
              </div>

              <SpreadKlineChart candles={cs} timeframe={klineTf} stats={klineData.stats} />
            </>
          );
        })()}
      </Modal>
    </div>
  );
}
