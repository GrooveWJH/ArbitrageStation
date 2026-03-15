import React from 'react';
import { Space, Tag } from 'antd';
import { usePriceDiff } from './priceDiffStore';
import { formatCountdown, periodLabel } from './utils';

export function LongCell({ record }) {
  const pd = usePriceDiff(record.symbol, record.long_exchange_id, record.short_exchange_id);
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

export function ShortCell({ record }) {
  const pd = usePriceDiff(record.symbol, record.long_exchange_id, record.short_exchange_id);
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

export function PriceDiffCell({ record }) {
  const pd = usePriceDiff(record.symbol, record.long_exchange_id, record.short_exchange_id);
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
