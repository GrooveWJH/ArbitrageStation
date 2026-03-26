import React from 'react';
import { Space, Tag } from 'antd';
import ExchangeLogoName from '../../components/ExchangeLogoName';
import { usePriceDiff } from './priceDiffStore';
import { formatCountdown, periodLabel } from './utils';

function priceDiffTone(value) {
  if (Math.abs(value) > 0.3) return 'kinetic-num-negative';
  if (Math.abs(value) > 0.1) return 'kinetic-num-warning';
  return 'kinetic-num-positive';
}

export function LongCell({ record }) {
  const pd = usePriceDiff(record.symbol, record.long_exchange_id, record.short_exchange_id);
  const lp = record.long_periods_per_day;
  const sp = record.short_periods_per_day;
  const isLower = lp != null && sp != null && lp < sp;

  return (
    <div className={`kinetic-leg-cell ${isLower ? 'is-mismatch' : ''}`}>
      <Space size={4}>
        <Tag className={`kinetic-exchange-chip ${isLower ? 'is-warning' : ''}`}>
          <ExchangeLogoName name={record.long_exchange} exchangeId={record.long_exchange_id} />
        </Tag>
        <span className={`kinetic-num ${record.long_rate_pct < 0 ? 'kinetic-num-positive' : 'kinetic-num-negative'}`}>
          {record.long_rate_pct > 0 ? '+' : ''}
          {record.long_rate_pct?.toFixed(4)}%
        </span>
      </Space>
      <div className={`kinetic-leg-sub ${isLower ? 'is-warning' : ''}`}>
        {periodLabel(lp)} · {formatCountdown(record.long_next_funding_time)}
      </div>
      {pd?.long_price ? <div className="kinetic-price-note">${pd.long_price.toLocaleString()}</div> : null}
    </div>
  );
}

export function ShortCell({ record }) {
  const pd = usePriceDiff(record.symbol, record.long_exchange_id, record.short_exchange_id);
  const lp = record.long_periods_per_day;
  const sp = record.short_periods_per_day;
  const isLower = sp != null && lp != null && sp < lp;

  return (
    <div className={`kinetic-leg-cell ${isLower ? 'is-mismatch' : ''}`}>
      <Space size={4}>
        <Tag className={`kinetic-exchange-chip ${isLower ? 'is-warning' : ''}`}>
          <ExchangeLogoName name={record.short_exchange} exchangeId={record.short_exchange_id} />
        </Tag>
        <span className="kinetic-num kinetic-num-negative">
          {record.short_rate_pct > 0 ? '+' : ''}
          {record.short_rate_pct?.toFixed(4)}%
        </span>
      </Space>
      <div className={`kinetic-leg-sub ${isLower ? 'is-warning' : ''}`}>
        {periodLabel(sp)} · {formatCountdown(record.short_next_funding_time)}
      </div>
      {pd?.short_price ? <div className="kinetic-price-note">${pd.short_price.toLocaleString()}</div> : null}
    </div>
  );
}

export function PriceDiffCell({ record }) {
  const pd = usePriceDiff(record.symbol, record.long_exchange_id, record.short_exchange_id);
  const value = pd?.price_diff_pct ?? record.price_diff_pct;
  if (value == null) return <span className="kinetic-num kinetic-num-muted">-</span>;

  return (
    <span className={`kinetic-num ${priceDiffTone(value)}`}>
      {value > 0 ? '+' : ''}
      {value.toFixed(4)}%
    </span>
  );
}
