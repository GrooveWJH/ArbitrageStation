import { composeSpreadRowClass, isWithinSpreadGroup } from './rowHover';

describe('spread row hover helpers', () => {
  test('compose row class merges highfreq and group hover state', () => {
    const cls = composeSpreadRowClass({ is_highest_freq: true, _groupKey: 'LRC/USDT' }, 'LRC/USDT');
    expect(cls).toContain('kinetic-spread-row-highfreq');
    expect(cls).toContain('kinetic-spread-row-group-hover');
  });

  test('group hover persists when pointer moves within same group row set', () => {
    document.body.innerHTML = '<table><tbody><tr data-group-key="LRC/USDT"><td id="hit"></td></tr></tbody></table>';
    const target = document.getElementById('hit');
    expect(isWithinSpreadGroup('LRC/USDT', target)).toBe(true);
    expect(isWithinSpreadGroup('BARD/USDT', target)).toBe(false);
  });
});
