import React from 'react';
import { Tag, Tooltip } from 'antd';

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
  const SETTLED_FLASH_SECONDS = 3;
  const REFRESH_WAIT_SECONDS = 10 * 60;
  if (!nextFundingTime) return <Tag className="kinetic-countdown-tag is-unsynced">未同步</Tag>;

  const targetMs = new Date(nextFundingTime).getTime();
  if (!Number.isFinite(targetMs)) return <Tag className="kinetic-countdown-tag is-unsynced">未同步</Tag>;

  const secs = Math.floor((targetMs - Date.now()) / 1000);
  if (secs <= 0) {
    if (Math.abs(secs) <= SETTLED_FLASH_SECONDS) {
      return <Tag className="kinetic-countdown-tag is-settled is-settled-flash">刚结算</Tag>;
    }
    const waited = Math.abs(secs);
    const remain = Math.max(REFRESH_WAIT_SECONDS - waited, 0);
    const progress = Math.max(0, Math.min(waited / REFRESH_WAIT_SECONDS, 1));
    const mm = Math.floor(remain / 60);
    const ss = remain % 60;
    const remainText = `${mm}m ${String(ss).padStart(2, '0')}s`;
    return (
      <Tooltip title={`预计 ${remainText} 后触发更新`}>
        <Tag
          className="kinetic-countdown-tag is-refresh-pending has-progress"
          style={{ '--kinetic-refresh-progress': `${Math.round(progress * 100)}%` }}
        >
          <span className="kinetic-countdown-tag-label">待更新</span>
        </Tag>
      </Tooltip>
    );
  }

  const h = Math.floor(secs / 3600);
  const m = Math.floor((secs % 3600) / 60);
  const s = secs % 60;
  const level = secs < 600 ? 'kinetic-countdown-danger' : secs < 1800 ? 'kinetic-countdown-warn' : 'kinetic-countdown-neutral';
  const text = h > 0 ? `${h}h ${String(m).padStart(2, '0')}m` : `${m}m ${String(s).padStart(2, '0')}s`;

  return <span className={`kinetic-countdown ${level}`}>{text}</span>;
}

export function periodLabel(p) {
  if (!p) return '周期未知';
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

export function getOpportunitySignal(record) {
  const annualized = Number(record?.annualized_pct || 0);
  const priceDiff = Math.abs(Number(record?.price_diff_pct || 0));
  if (priceDiff >= 1) return 'risk';
  if (annualized >= 250) return 'hot';
  return null;
}

export function formatPairBase(symbol) {
  const raw = String(symbol || '').trim();
  if (!raw) return '-';

  const droppedQuote = raw
    .replace(/:USDT$/i, '')
    .replace(/[\/:_-]USDT$/i, '')
    .replace(/USDT$/i, '');

  return droppedQuote.replace(/[\/:_-]$/, '') || raw;
}
