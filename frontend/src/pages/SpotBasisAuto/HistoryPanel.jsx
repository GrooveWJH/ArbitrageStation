import React, {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import {
  Button,
  Empty,
  Segmented,
  Space,
  Tag,
} from 'antd';
import { ReloadOutlined } from '@ant-design/icons';
import { getSpotBasisHistory } from '../../services/endpoints/spotBasisApi';
import { getApiErrorMessage } from '../../utils/error';
import { fmtTime, keyOf, num } from './helpers';

const PAD = { left: 58, right: 64, top: 10, bottom: 34 };
const HISTORY_CACHE_TTL_MS = 60 * 1000;
const historyCache = new Map();

const makeTicks = (min, max, count = 5) => {
  if (!Number.isFinite(min) || !Number.isFinite(max)) return [0];
  if (Math.abs(max - min) < 1e-12) return [min];
  const out = [];
  for (let i = 0; i < count; i += 1) out.push(min + ((max - min) * i) / (count - 1));
  return out;
};

const autoRange = (values, fallbackSpan = 1) => {
  const clean = values.filter((v) => Number.isFinite(v));
  if (!clean.length) return [-fallbackSpan, fallbackSpan];
  const min = Math.min(...clean);
  const max = Math.max(...clean);
  if (Math.abs(max - min) < 1e-10) {
    const mid = (min + max) / 2;
    const span = Math.max(Math.abs(mid) * 0.2, 0.02, fallbackSpan * 0.1);
    return [mid - span, mid + span];
  }
  const pad = (max - min) * 0.12;
  return [min - pad, max + pad];
};

const buildPath = (values, toX, toY) => {
  let d = '';
  let open = false;
  values.forEach((v, i) => {
    if (!Number.isFinite(v)) {
      open = false;
      return;
    }
    d += `${open ? 'L' : 'M'} ${toX(i)} ${toY(v)} `;
    open = true;
  });
  return d.trim();
};

function DualAxisChart({ series }) {
  const host = useRef(null);
  const [width, setWidth] = useState(900);

  useEffect(() => {
    if (!host.current) return undefined;
    const ro = new ResizeObserver(() => {
      const next = Math.floor(host.current?.clientWidth || 900);
      setWidth((prev) => (Math.abs(prev - next) > 1 ? next : prev));
    });
    ro.observe(host.current);
    return () => ro.disconnect();
  }, []);

  if (!series.length) return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无详情数据" />;

  const innerW = Math.max(10, width - PAD.left - PAD.right);
  const innerH = 232;
  const basis = series.map((x) => num(x.basis_pct, Number.NaN));
  const funding = series.map((x) => (x.funding_rate_pct == null ? Number.NaN : num(x.funding_rate_pct, Number.NaN)));
  const [leftMin, leftMax] = autoRange(basis, 0.4);
  const [rightMin, rightMax] = autoRange(funding, 0.06);
  const leftTicks = makeTicks(leftMin, leftMax, 5);
  const rightTicks = makeTicks(rightMin, rightMax, 5);
  const toX = (i) => PAD.left + (innerW * i) / Math.max(1, series.length - 1);
  const toYLeft = (v) => PAD.top + innerH * (1 - (v - leftMin) / Math.max(1e-12, leftMax - leftMin));
  const toYRight = (v) => PAD.top + innerH * (1 - (v - rightMin) / Math.max(1e-12, rightMax - rightMin));
  const basisPath = buildPath(basis, toX, toYLeft);
  const fundingPath = buildPath(funding, toX, toYRight);
  const xLabels = [...new Set([0, Math.floor((series.length - 1) / 2), series.length - 1])];

  return (
    <div ref={host} style={{ width: '100%' }}>
      <svg width={width} height={300}>
        {leftTicks.map((t) => (
          <line key={`grid-${t}`} x1={PAD.left} x2={PAD.left + innerW} y1={toYLeft(t)} y2={toYLeft(t)} stroke="#2f467a" strokeDasharray="3 3" />
        ))}
        <line x1={PAD.left} x2={PAD.left} y1={PAD.top} y2={PAD.top + innerH} stroke="#47639a" />
        <line x1={PAD.left + innerW} x2={PAD.left + innerW} y1={PAD.top} y2={PAD.top + innerH} stroke="#47639a" />
        <path d={basisPath} fill="none" stroke="#f59e0b" strokeWidth="2" />
        <path d={fundingPath} fill="none" stroke="#06b6d4" strokeWidth="2" />
        {series.length === 1 && Number.isFinite(basis[0]) && <circle cx={toX(0)} cy={toYLeft(basis[0])} r="3" fill="#f59e0b" />}
        {series.length === 1 && Number.isFinite(funding[0]) && <circle cx={toX(0)} cy={toYRight(funding[0])} r="3" fill="#06b6d4" />}

        {leftTicks.map((t) => (
          <text key={`ly-${t}`} x={PAD.left - 8} y={toYLeft(t) + 4} textAnchor="end" fill="#f59e0b" fontSize={11}>
            {`${num(t, 0).toFixed(3)}%`}
          </text>
        ))}
        {rightTicks.map((t) => (
          <text key={`ry-${t}`} x={PAD.left + innerW + 8} y={toYRight(t) + 4} textAnchor="start" fill="#06b6d4" fontSize={11}>
            {`${num(t, 0).toFixed(3)}%`}
          </text>
        ))}
        {xLabels.map((idx) => (
          <text key={`tx-${idx}`} x={toX(idx)} y={PAD.top + innerH + 20} textAnchor="middle" fill="#8ea4d4" fontSize={11}>
            {fmtTime(num(series[idx]?.time, Number.NaN))}
          </text>
        ))}
      </svg>
    </div>
  );
}

function mergeHistory(payload) {
  const fundingSeries = (payload?.funding_series || [])
    .map((x) => ({ t: num(x.time, Number.NaN), v: x.rate_pct == null ? null : num(x.rate_pct, Number.NaN) }))
    .filter((x) => Number.isFinite(x.t) && Number.isFinite(x.v))
    .sort((a, b) => a.t - b.t);

  let idx = 0;
  let last = null;
  return (payload?.series || []).map((x) => {
    const t = num(x.time, 0);
    while (idx < fundingSeries.length && fundingSeries[idx].t <= t) {
      last = fundingSeries[idx].v;
      idx += 1;
    }
    return { ...x, funding_rate_pct: last };
  });
}

export default function HistoryPanel({ row }) {
  const [timeframe, setTimeframe] = useState('1h');
  const [loading, setLoading] = useState(false);
  const [series, setSeries] = useState([]);
  const [err, setErr] = useState('');
  const reqRef = useRef(0);
  const rowKey = useMemo(() => keyOf(row), [row]);

  const load = useCallback(async (tf, force = false) => {
    const cacheKey = `${rowKey}|${tf}`;
    const cached = historyCache.get(cacheKey);
    if (!force && cached && Date.now() - cached.ts <= HISTORY_CACHE_TTL_MS) {
      setSeries(cached.series);
      setErr('');
      return;
    }

    reqRef.current += 1;
    const reqId = reqRef.current;
    setLoading(true);
    setErr('');
    try {
      const { data } = await getSpotBasisHistory({
        symbol: row.symbol,
        perp_exchange_id: row.perp_exchange_id,
        spot_exchange_id: row.spot_exchange_id,
        timeframe: tf,
        limit: 260,
      });
      if (reqRef.current !== reqId) return;
      const merged = mergeHistory(data);
      setSeries(merged);
      historyCache.set(cacheKey, { ts: Date.now(), series: merged });
    } catch (e) {
      if (reqRef.current !== reqId) return;
      setErr(getApiErrorMessage(e, '加载失败'));
    } finally {
      if (reqRef.current === reqId) setLoading(false);
    }
  }, [row, rowKey]);

  useEffect(() => {
    void load(timeframe, false);
  }, [load, timeframe]);

  return (
    <div style={{ padding: 8, background: 'rgba(6, 18, 45, 0.78)', borderRadius: 8, border: '1px solid rgba(43, 70, 128, 0.7)' }}>
      <Space style={{ marginBottom: 8 }} wrap>
        <Tag color="blue">{row.symbol}</Tag>
        <Tag>{row.perp_exchange_name} 合约</Tag>
        <Tag>{row.spot_exchange_name} 现货</Tag>
        <Segmented
          size="small"
          value={timeframe}
          onChange={setTimeframe}
          options={[
            { label: '5m', value: '5m' },
            { label: '15m', value: '15m' },
            { label: '1h', value: '1h' },
            { label: '4h', value: '4h' },
          ]}
        />
        <Button size="small" icon={<ReloadOutlined />} onClick={() => { void load(timeframe, true); }}>
          刷新
        </Button>
        {loading && <Tag color="processing">加载中</Tag>}
        {err && <Tag color="error">{err}</Tag>}
      </Space>

      <Space size={14} style={{ marginBottom: 6 }}>
        <Space size={6}>
          <span style={{ display: 'inline-block', width: 12, height: 3, borderRadius: 2, background: '#f59e0b' }} />
          <span style={{ color: '#9fb5e8', fontSize: 12 }}>基差(%) 左轴</span>
        </Space>
        <Space size={6}>
          <span style={{ display: 'inline-block', width: 12, height: 3, borderRadius: 2, background: '#06b6d4' }} />
          <span style={{ color: '#9fb5e8', fontSize: 12 }}>费率(%) 右轴</span>
        </Space>
      </Space>

      <DualAxisChart series={series} />
    </div>
  );
}
