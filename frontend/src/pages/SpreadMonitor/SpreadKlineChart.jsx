import React, {
  useEffect,
  useRef,
  useState,
} from 'react';

const PAD = { left: 68, right: 16, top: 12, bottom: 52 };
const CHART_H = 300;

function niceYTicks(minV, maxV, count = 6) {
  const range = maxV - minV || 1;
  const raw = range / (count - 1);
  const mag = Math.pow(10, Math.floor(Math.log10(raw)));
  const step = [1, 2, 2.5, 5, 10].map((f) => f * mag).find((s) => s >= raw) || raw;
  const lo = Math.floor(minV / step) * step;
  const ticks = [];
  for (let t = lo; t <= maxV + step * 0.01; t = Math.round((t + step) * 1e8) / 1e8) {
    ticks.push(parseFloat(t.toFixed(8)));
    if (ticks.length > count + 2) break;
  }
  return ticks.filter((t) => t >= minV - step * 0.5 && t <= maxV + step * 0.5);
}

export default function SpreadKlineChart({
  candles,
  timeframe,
  stats,
}) {
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

  const cw = width - PAD.left - PAD.right;
  const ch = CHART_H;
  const allV = candles.flatMap((c) => [c.open, c.high, c.low, c.close]);
  const rawMin = Math.min(...allV);
  const rawMax = Math.max(...allV);
  const pad = (rawMax - rawMin) * 0.08 || 0.5;
  const yMin = rawMin - pad;
  const yMax = rawMax + pad;
  const toY = (v) => PAD.top + ch * (1 - (v - yMin) / (yMax - yMin));

  const n = candles.length;
  const slotW = cw / n;
  const bodyW = Math.max(1, Math.min(16, slotW * 0.65));
  const xOf = (i) => PAD.left + (i + 0.5) * slotW;
  const maxLabels = Math.max(4, Math.floor(cw / 80));
  const labelStep = Math.max(1, Math.ceil(n / maxLabels));
  const yTicks = niceYTicks(yMin, yMax, 6);

  const fmtX = (ts) => {
    const d = new Date(ts);
    if (timeframe === '1d') return `${d.getMonth() + 1}/${d.getDate()}`;
    return `${String(d.getMonth() + 1).padStart(2, '0')}/${String(d.getDate()).padStart(2, '0')} ${String(d.getHours()).padStart(2, '0')}:${String(d.getMinutes()).padStart(2, '0')}`;
  };

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
        {yTicks.map((t, i) => {
          const y = toY(t);
          const isZero = Math.abs(t) < 0.0001;
          return (
            <g key={i}>
              <line
                x1={PAD.left}
                x2={PAD.left + cw}
                y1={y}
                y2={y}
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

        {candles.map((c, i) => {
          const x = xOf(i);
          const isUp = c.close >= c.open;
          const color = isUp ? '#ef5350' : '#26a69a';
          const bodyTop = toY(Math.max(c.open, c.close));
          const bodyBot = toY(Math.min(c.open, c.close));
          const bodyH = Math.max(1.5, bodyBot - bodyTop);
          const isHov = hoverIdx === i;
          return (
            <g key={i} opacity={hoverIdx != null && !isHov ? 0.5 : 1}>
              {isHov && (
                <rect x={x - slotW / 2} y={PAD.top} width={slotW} height={ch} fill="#f5f5f5" opacity={0.5} />
              )}
              <line x1={x} x2={x} y1={toY(c.high)} y2={toY(c.low)} stroke={color} strokeWidth={1.2} />
              <rect x={x - bodyW / 2} y={bodyTop} width={bodyW} height={bodyH} fill={color} stroke={color} strokeWidth={0.5} />
            </g>
          );
        })}

        {hov && (
          <line
            x1={xOf(hoverIdx)}
            x2={xOf(hoverIdx)}
            y1={PAD.top}
            y2={PAD.top + ch}
            stroke="#999"
            strokeWidth={1}
            strokeDasharray="3,3"
          />
        )}

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

        {candles.map((c, i) => {
          if (i % labelStep !== 0) return null;
          const x = xOf(i);
          return (
            <text
              key={i}
              x={x}
              y={PAD.top + ch + 18}
              textAnchor="middle"
              fontSize={10}
              fill="#aaa"
              transform={`rotate(-35, ${x}, ${PAD.top + ch + 18})`}
            >
              {fmtX(c.time)}
            </text>
          );
        })}

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
          const bw = 130;
          const bh = lines.length * 16 + 10;
          const bx = x + 12 + bw > PAD.left + cw ? x - bw - 12 : x + 12;
          const by = Math.max(PAD.top, Math.min(PAD.top + ch - bh, toY(hov.high) - 10));
          return (
            <g>
              <rect x={bx} y={by} width={bw} height={bh} rx={4} fill="white" stroke="#e0e0e0" strokeWidth={1} filter="url(#shadow)" />
              {lines.map((l, li) => (
                <text key={li} x={bx + 8} y={by + 14 + li * 16} fontSize={11} fill={li === 0 ? '#666' : li === 4 ? color : '#333'} fontWeight={li === 4 ? 600 : 400}>
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
