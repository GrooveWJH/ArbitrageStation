const {
  KINETIC_STATUS_TONE,
  KINETIC_THEME_TOKENS,
  buildPageChromeConfig,
} = require('./kineticTheme');

describe('kineticTheme', () => {
  test('exposes required public theme interfaces', () => {
    expect(KINETIC_THEME_TOKENS).toBeDefined();
    expect(KINETIC_THEME_TOKENS.colors.primary).toBe('#7bd0ff');
    expect(KINETIC_THEME_TOKENS.fonts.headline).toContain('Manrope');
    expect(KINETIC_STATUS_TONE.live).toBe('live');
  });

  test('builds dashboard chrome config with live status', () => {
    const config = buildPageChromeConfig('dashboard');
    expect(config.title).toBe('总览看板');
    expect(config.badge).toBe('系统主控台');
    expect(config.statusTone).toBe('live');
    expect(config.statusText).toContain('实时');
  });

  test('builds settings chrome config with stable status', () => {
    const config = buildPageChromeConfig('settings');
    expect(config.title).toBe('系统设置');
    expect(config.statusTone).toBe('stable');
  });
});
