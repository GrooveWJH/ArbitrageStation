import React from 'react';
import { buildOppColumns, buildSpotOppColumns } from './columns';
import { LongCell } from './OpportunityCells';
import { formatCountdown } from './utils';

jest.mock('./priceDiffStore', () => ({
  usePriceDiff: () => null,
}));

describe('dashboard opportunities UI metrics', () => {
  test('rate diff cell uses kinetic numeric classes', () => {
    const columns = buildOppColumns();
    const rateDiffColumn = columns.find((col) => col.key === 'rate_diff_pct');
    const node = rateDiffColumn.render(0.4281);

    expect(node.props.className).toContain('kinetic-num');
    expect(node.props.className).toContain('kinetic-num-positive');
  });

  test('countdown renders danger class when settlement is near', () => {
    const nearFuture = new Date(Date.now() + 5 * 60 * 1000).toISOString();
    const node = formatCountdown(nearFuture);

    expect(node.props.className).toContain('kinetic-countdown');
    expect(node.props.className).toContain('kinetic-countdown-danger');
  });

  test('countdown shows unsynced tag when funding time is missing', () => {
    const node = formatCountdown(null);
    expect(node.props.className).toContain('kinetic-countdown-tag');
    expect(node.props.className).toContain('is-unsynced');
    expect(node.props.children).toBe('未同步');
  });

  test('countdown shows recent settled only in short window', () => {
    const node = formatCountdown(new Date(Date.now() - 1 * 1000).toISOString());
    expect(node.props.className).toContain('kinetic-countdown-tag');
    expect(node.props.className).toContain('is-settled');
    expect(node.props.className).toContain('is-settled-flash');
    expect(node.props.children).toBe('刚结算');
  });

  test('countdown switches to pending after settled flash window', () => {
    const node = formatCountdown(new Date(Date.now() - 10 * 1000).toISOString());
    const tagNode = node.props.children;
    expect(tagNode.props.className).toContain('is-refresh-pending');
  });

  test('countdown falls back to pending refresh when settlement timestamp is stale', () => {
    const node = formatCountdown(new Date(Date.now() - 10 * 60 * 1000).toISOString());
    const tagNode = node.props.children;
    const labelNode = React.Children.only(tagNode.props.children);

    expect(tagNode.props.className).toContain('kinetic-countdown-tag');
    expect(tagNode.props.className).toContain('is-refresh-pending');
    expect(tagNode.props.className).toContain('has-progress');
    expect(String(tagNode.props.style['--kinetic-refresh-progress'])).toContain('%');
    expect(node.props.title).toContain('后触发更新');
    expect(labelNode.props.children).toBe('待更新');
  });

  test('long leg highlights period mismatch via class name', () => {
    const node = LongCell({
      record: {
        symbol: 'BTC/USDT',
        long_exchange: 'BINANCE',
        short_exchange: 'OKX',
        long_exchange_id: 'binance',
        short_exchange_id: 'okx',
        long_periods_per_day: 2,
        short_periods_per_day: 3,
        long_rate_pct: -0.1234,
        long_next_funding_time: new Date(Date.now() + 60 * 60 * 1000).toISOString(),
      },
    });

    expect(node.props.className).toContain('kinetic-leg-cell');
    expect(node.props.className).toContain('is-mismatch');
  });

  test('long leg exchange cell renders logo identity component', () => {
    const node = LongCell({
      record: {
        symbol: 'BTC/USDT',
        long_exchange: 'OKX',
        short_exchange: 'BINANCE',
        long_exchange_id: 'okx',
        short_exchange_id: 'binance',
        long_periods_per_day: 3,
        short_periods_per_day: 3,
        long_rate_pct: -0.02,
        long_next_funding_time: new Date(Date.now() + 60 * 60 * 1000).toISOString(),
      },
    });

    const space = React.Children.toArray(node.props.children)[0];
    const exchangeTag = React.Children.toArray(space.props.children)[0];
    const exchangeIdentity = exchangeTag.props.children;

    expect(exchangeIdentity.type.name).toBe('ExchangeLogoName');
    expect(exchangeIdentity.props.exchangeId).toBe('okx');
  });

  test('table numeric sorters use natural ascending comparator', () => {
    const oppColumns = buildOppColumns();
    const spotColumns = buildSpotOppColumns();

    const oppRateDiff = oppColumns.find((col) => col.key === 'rate_diff_pct');
    const oppVolume = oppColumns.find((col) => col.key === 'min_volume_24h');
    const spotAnnualized = spotColumns.find((col) => col.key === 'annualized_pct');
    const spotPerpVol = spotColumns.find((col) => col.key === 'volume_24h');

    expect(oppRateDiff.sorter({ rate_diff_pct: 3 }, { rate_diff_pct: 1 })).toBeGreaterThan(0);
    expect(oppVolume.sorter({ min_volume_24h: 9e6 }, { min_volume_24h: 1e6 })).toBeGreaterThan(0);
    expect(spotAnnualized.sorter({ annualized_pct: 200 }, { annualized_pct: 50 })).toBeGreaterThan(0);
    expect(spotPerpVol.sorter({ volume_24h: 8e6 }, { volume_24h: 1e6 })).toBeGreaterThan(0);
  });

  test('right-side numeric columns are center aligned in opportunities table', () => {
    const columns = buildOppColumns();
    const keys = ['rate_diff_pct', 'annualized_pct', 'price_diff_pct', 'min_volume_24h'];
    keys.forEach((key) => {
      expect(columns.find((col) => col.key === key)?.align).toBe('center');
    });
  });

  test('left-side identity columns are left aligned in opportunities table', () => {
    const columns = buildOppColumns();
    const keys = ['signal', 'symbol', 'long', 'short'];
    keys.forEach((key) => {
      expect(columns.find((col) => col.key === key)?.align).toBe('left');
    });
  });

  test('annualized column uses high-green and mid-blue palette', () => {
    const columns = buildOppColumns();
    const annualizedCol = columns.find((col) => col.key === 'annualized_pct');
    const highNode = annualizedCol.render(430.34);
    const midNode = annualizedCol.render(195.35);

    expect(highNode.props.className).toContain('kinetic-num-positive');
    expect(midNode.props.className).toContain('kinetic-num-strong');
  });

  test('opportunity table renders explicit signal column', () => {
    const columns = buildOppColumns();
    const signalColumn = columns.find((col) => col.key === 'signal');
    const riskNode = signalColumn.render(null, { annualized_pct: 320, price_diff_pct: 1.2 });
    const hotNode = signalColumn.render(null, { annualized_pct: 320, price_diff_pct: 0.2 });

    expect(signalColumn.title).toBe('信号');
    expect(signalColumn.width).toBeGreaterThanOrEqual(130);
    expect(riskNode.props.className).toContain('kinetic-opportunity-signal');
    expect(riskNode.props.className).toContain('is-risk');
    expect(hotNode.props.className).toContain('is-hot');
  });

  test('symbol cell keeps clean single pair chip without duplicated signal icon', () => {
    const columns = buildOppColumns();
    const symbolColumn = columns.find((col) => col.key === 'symbol');
    const node = symbolColumn.render('LRC/USDT', { annualized_pct: 280, price_diff_pct: 0.2 });

    expect(symbolColumn.width).toBeGreaterThanOrEqual(180);
    expect(symbolColumn.title).toContain('USDT');
    expect(node.props.className).toContain('kinetic-pair-chip');
    expect(node.props.className).toContain('kinetic-opp-pair-chip');
    expect(node.props.children).toBe('LRC');
  });
});
