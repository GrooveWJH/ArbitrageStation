import React from 'react';
import { buildFundingColumns } from './columns';

describe('funding rates exchange branding', () => {
  test('exchange column renders logo identity component', () => {
    const columns = buildFundingColumns([{ id: 'okx', display_name: 'OKX' }]);
    const exchangeColumn = columns.find((col) => col.dataIndex === 'exchange_name');
    const node = exchangeColumn.render('OKX', { exchange_id: 'okx', exchange_name: 'OKX' });
    const exchangeIdentity = node.props.children;

    expect(exchangeIdentity.type.name).toBe('ExchangeLogoName');
    expect(exchangeIdentity.props.exchangeId).toBe('okx');
  });

  test('numeric sorters follow ascend/descend semantics', () => {
    const columns = buildFundingColumns([]);
    const rateColumn = columns.find((col) => col.key === 'rate_pct');
    const absRateColumn = columns.find((col) => col.key === 'abs_rate');
    const annualizedColumn = columns.find((col) => col.key === 'annualized');
    const volumeColumn = columns.find((col) => col.key === 'volume_24h');

    expect(rateColumn.sorter({ rate_pct: 5 }, { rate_pct: 1 })).toBeGreaterThan(0);
    expect(absRateColumn.sorter({ rate_pct: -5 }, { rate_pct: 1 })).toBeGreaterThan(0);
    expect(annualizedColumn.sorter({ rate_pct: -0.2 }, { rate_pct: 0.1 })).toBeGreaterThan(0);
    expect(volumeColumn.sorter({ volume_24h: 5e6 }, { volume_24h: 1e6 })).toBeGreaterThan(0);
  });

  test('annualized column renders non-negative magnitude', () => {
    const columns = buildFundingColumns([]);
    const annualizedColumn = columns.find((col) => col.key === 'annualized');
    const node = annualizedColumn.render(null, { rate_pct: -0.2 });

    expect(node.props.children).toBe('219.0%');
    expect(String(node.props.className)).toContain('kinetic-num-positive');
  });
});
