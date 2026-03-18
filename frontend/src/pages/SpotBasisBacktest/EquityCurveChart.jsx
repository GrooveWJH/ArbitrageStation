import React, {
  useEffect,
  useRef,
  useState,
} from 'react';
import { Empty } from 'antd';
import { num } from './utils';

export default function EquityCurveChart({ rows }) {
  const hostRef = useRef(null);
  const [width, setWidth] = useState(960);

  useEffect(() => {
    if (!hostRef.current) return undefined;
    const ro = new ResizeObserver(() => {
      const next = Math.floor(hostRef.current?.clientWidth || 960);
      setWidth((prev) => (Math.abs(prev - next) > 1 ? next : prev));
    });
    ro.observe(hostRef.current);
    return () => ro.disconnect();
  }, []);

  if (!rows?.length) return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无权益曲线" />;

  const data = rows.map((x) => num(x.equity_usd, Number.NaN));
  const clean = data.filter((x) => Number.isFinite(x));
  if (!clean.length) return <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="暂无有效权益数据" />;

  const minV = Math.min(...clean);
  const maxV = Math.max(...clean);
  const span = Math.max(1e-9, maxV - minV);
  const pad = span * 0.12;
  const lo = minV - pad;
  const hi = maxV + pad;
  const PAD = { left: 58, right: 20, top: 12, bottom: 30 };
  const H = 260;
  const innerW = Math.max(20, width - PAD.left - PAD.right);
  const innerH = H - PAD.top - PAD.bottom;

  const toX = (i) => PAD.left + (innerW * i) / Math.max(1, data.length - 1);
  const toY = (v) => PAD.top + innerH * (1 - (v - lo) / Math.max(1e-9, hi - lo));

  let d = '';
  let open = false;
  data.forEach((v, i) => {
    if (!Number.isFinite(v)) {
      open = false;
      return;
    }
    d += `${open ? 'L' : 'M'} ${toX(i)} ${toY(v)} `;
    open = true;
  });

  const ticks = [0, 0.25, 0.5, 0.75, 1].map((p) => lo + (hi - lo) * p);

  return (
    <div ref={hostRef} style={{ width: '100%' }}>
      <svg width={width} height={H}>
        {ticks.map((v) => (
          <line
            key={`g-${v}`}
            x1={PAD.left}
            x2={PAD.left + innerW}
            y1={toY(v)}
            y2={toY(v)}
            stroke="#e2e8f0"
            strokeDasharray="3 3"
          />
        ))}
        <line x1={PAD.left} x2={PAD.left} y1={PAD.top} y2={PAD.top + innerH} stroke="#cbd5e1" />
        <line x1={PAD.left} x2={PAD.left + innerW} y1={PAD.top + innerH} y2={PAD.top + innerH} stroke="#cbd5e1" />
        <path d={d.trim()} fill="none" stroke="#1677ff" strokeWidth="2" />
        {ticks.map((v) => (
          <text key={`t-${v}`} x={PAD.left - 8} y={toY(v) + 4} textAnchor="end" fontSize={11} fill="#64748b">
            {v.toFixed(2)}
          </text>
        ))}
        <text x={PAD.left} y={H - 8} fill="#64748b" fontSize={11}>开始</text>
        <text x={PAD.left + innerW} y={H - 8} fill="#64748b" fontSize={11} textAnchor="end">结束</text>
      </svg>
    </div>
  );
}
