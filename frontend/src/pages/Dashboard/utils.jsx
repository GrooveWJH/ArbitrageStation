import React from 'react';
import { Tag } from 'antd';

export function toNumber(v) {
  const n = Number(v);
  return Number.isFinite(n) ? n : 0;
}

export function calcExchangeTotalUsdt(exchangeRow) {
  if (!exchangeRow) return 0;
  const totalUsdt = toNumber(exchangeRow.total_usdt);
  if (totalUsdt > 0) return totalUsdt;
  if (exchangeRow.unified_account) return totalUsdt;
  return toNumber(exchangeRow.spot_usdt) + toNumber(exchangeRow.futures_usdt);
}

export function formatUsdt(v, precision = 2) {
  return Number(v || 0).toLocaleString(undefined, {
    minimumFractionDigits: precision,
    maximumFractionDigits: precision,
  });
}

export function formatCountdown(nextFundingTime) {
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

export function periodLabel(p) {
  if (!p) return '-';
  const h = 24 / p;
  const hStr = h === Math.floor(h) ? `${h}h` : `${h.toFixed(1)}h`;
  return `每${hStr} · ${p}次/天`;
}

export function formatVolume(v) {
  if (!(v > 0)) return '-';
  if (v >= 1e9) return `${(v / 1e9).toFixed(1)}B`;
  if (v >= 1e6) return `${(v / 1e6).toFixed(1)}M`;
  return `${(v / 1e3).toFixed(0)}K`;
}
