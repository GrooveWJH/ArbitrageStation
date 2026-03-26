import React from 'react';
import SortHeader from './SortHeader';
import { buildColumns } from './columns';

describe('spread monitor theme classes', () => {
  test('sort header keeps active direction class after selection', () => {
    const node = SortHeader({
      label: '合约价差',
      tooltip: '按合约价差排序',
      field: 'spread',
      sortField: 'spread',
      sortDir: 'asc',
      onSort: jest.fn(),
    });

    const button = node.props.children;
    const children = React.Children.toArray(button.props.children);
    const orderLabel = children[1];
    const iconWrap = children[2];
    const upIcon = React.Children.toArray(iconWrap.props.children)[0];
    const downIcon = React.Children.toArray(iconWrap.props.children)[1];

    expect(button.props.className).toContain('kinetic-sort-header');
    expect(button.props.className).toContain('is-active');
    expect(button.props.className).toContain('dir-asc');
    expect(orderLabel.props.className).toContain('kinetic-sort-order');
    expect(orderLabel.props.className).toContain('is-asc');
    expect(orderLabel.props.children).toBe('升序');
    expect(upIcon.props.className).toContain('is-on');
    expect(upIcon.type.displayName || upIcon.type.name).toBe('CaretUpOutlined');
    expect(downIcon.type.displayName || downIcon.type.name).toBe('CaretDownOutlined');
  });

  test('symbol and volume cells use semantic spread classes', () => {
    const columns = buildColumns({
      sortField: 'spread',
      sortDir: 'desc',
      onSort: jest.fn(),
      openKline: jest.fn(),
    });

    const symbolColumn = columns.find((col) => col.dataIndex === '_symbol');
    const volumeColumn = columns.find((col) => col.dataIndex === 'volume_24h');

    const symbolNode = symbolColumn.render('LRC/USDT', {
      _groupExchanges: [],
      _maxSpreadPct: 0.2377,
      _exchangeCount: 4,
    });
    const spreadPill = React.Children.toArray(symbolNode.props.children)[1];

    const volumeNode = volumeColumn.render(null, { _minVolume: 120000 });
    const volumeText = volumeNode.props.children;

    expect(spreadPill.props.className).toContain('kinetic-spread-spread-pill');
    expect(spreadPill.props.className).toContain('is-critical');
    expect(volumeText.props.className).toContain('kinetic-spread-volume');
    expect(volumeText.props.className).toContain('is-mid');
  });

  test('exchange column renders logo identity component', () => {
    const columns = buildColumns({
      sortField: 'spread',
      sortDir: 'desc',
      onSort: jest.fn(),
      openKline: jest.fn(),
    });
    const exchangeColumn = columns.find((col) => col.dataIndex === 'exchange_name');
    const node = exchangeColumn.render('GATE', { exchange_id: 'gate', is_highest_freq: false });
    const exchangeIdentity = React.Children.toArray(node.props.children)[0];

    expect(exchangeIdentity.type.name).toBe('ExchangeLogoName');
    expect(exchangeIdentity.props.className).toContain('kinetic-spread-exchange-name');
    expect(exchangeIdentity.props.exchangeId).toBe('gate');
  });
});
