import React from 'react';
import ExchangeLogoName, { resolveExchangeLogoKey } from './index';

describe('ExchangeLogoName', () => {
  test('resolves canonical keys and aliases', () => {
    expect(resolveExchangeLogoKey('OKX')).toBe('okx');
    expect(resolveExchangeLogoKey('mexc')).toBe('mexc');
    expect(resolveExchangeLogoKey('binance')).toBe('binance');
    expect(resolveExchangeLogoKey('gateio')).toBe('gate');
    expect(resolveExchangeLogoKey('gate.io')).toBe('gate');
  });

  test('renders logo-backed identity when key is known', () => {
    const node = ExchangeLogoName({ name: 'OKX', exchangeId: 'okx' });

    expect(node.props['data-exchange-key']).toBe('okx');
    expect(node.props['data-has-logo']).toBe('true');
  });

  test('falls back gracefully for unknown exchanges and keeps suffix', () => {
    const node = ExchangeLogoName({ name: 'BYBIT', suffix: '合约' });
    const children = React.Children.toArray(node.props.children);

    expect(node.props['data-exchange-key']).toBe('unknown');
    expect(node.props['data-has-logo']).toBe('false');
    expect(children[0].props.className).toContain('kinetic-exchange-logo-fallback');
    expect(children[2].props.children).toBe('合约');
  });
});
