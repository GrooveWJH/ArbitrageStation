const KINETIC_THEME_TOKENS = {
  colors: {
    background: '#060e20',
    surface: '#060e20',
    surfaceDim: '#060e20',
    surfaceContainerLow: '#06122d',
    surfaceContainer: '#05183c',
    surfaceContainerHigh: '#031d4b',
    surfaceContainerHighest: '#00225a',
    surfaceBright: '#002867',
    surfaceVariant: '#00225a',
    primary: '#7bd0ff',
    primaryDim: '#47c4ff',
    primaryContainer: '#004c69',
    secondary: '#8f9fb7',
    secondaryContainer: '#2d3c51',
    tertiary: '#c5ffc9',
    tertiaryDim: '#5bf083',
    tertiaryContainer: '#6bff8f',
    error: '#ee7d77',
    errorDim: '#bb5551',
    outline: '#5b74b1',
    outlineVariant: '#2b4680',
    textOnSurface: '#dee5ff',
    textOnSurfaceVariant: '#91aaeb',
  },
  fonts: {
    headline: '"Manrope", sans-serif',
    body: '"Inter", sans-serif',
    label: '"Space Grotesk", sans-serif',
  },
  radius: {
    sm: 2,
    md: 4,
    lg: 8,
  },
  shadows: {
    soft: '0 8px 24px rgba(3, 8, 24, 0.36)',
    focus: '0 0 0 2px rgba(123, 208, 255, 0.32)',
  },
};

const KINETIC_STATUS_TONE = {
  live: 'live',
  stable: 'stable',
  warning: 'warning',
  danger: 'danger',
  idle: 'idle',
};

const PAGE_CHROME = {
  dashboard: {
    badge: '系统主控台',
    title: '总览看板',
    subtitle: '跨所套利全局资产、盈亏、机会与成交状态总览',
    statusTone: KINETIC_STATUS_TONE.live,
    statusText: '实时连接正常',
  },
  'funding-rates': {
    badge: '费率矩阵',
    title: '资金费率',
    subtitle: '跨交易所资金费率与流动性强度监控',
    statusTone: KINETIC_STATUS_TONE.live,
    statusText: '行情流订阅中',
  },
  'spread-monitor': {
    badge: '价差引擎',
    title: '价差监控',
    subtitle: '实时观察多交易所价格偏离、成交量与对冲窗口',
    statusTone: KINETIC_STATUS_TONE.live,
    statusText: '价差流运行中',
  },
  opportunities: {
    badge: '机会雷达',
    title: '价差机会',
    subtitle: '发现并筛选可执行的跨所套利机会',
    statusTone: KINETIC_STATUS_TONE.live,
    statusText: '扫描中',
  },
  'spread-arb': {
    badge: '执行控制台',
    title: '价差套利',
    subtitle: '套利执行配置、仓位与风控联动控制台',
    statusTone: KINETIC_STATUS_TONE.stable,
    statusText: '策略服务稳定',
  },
  positions: {
    badge: '策略账本',
    title: '策略/持仓',
    subtitle: '策略生命周期、持仓质量与风险状态管理',
    statusTone: KINETIC_STATUS_TONE.stable,
    statusText: '仓位同步正常',
  },
  'spot-basis-auto': {
    badge: '自动化',
    title: '自动现货-合约费率套利',
    subtitle: '自动执行策略参数、状态与收益追踪',
    statusTone: KINETIC_STATUS_TONE.stable,
    statusText: '自动化运行中',
  },
  'spot-basis-backtest': {
    badge: '回测模拟',
    title: '现货-合约回测',
    subtitle: '策略参数回测、曲线分析与对照评估',
    statusTone: KINETIC_STATUS_TONE.idle,
    statusText: '等待任务',
  },
  analytics: {
    badge: '收益归因',
    title: '收益分析',
    subtitle: '收益归因、绩效拆解与策略质量分析',
    statusTone: KINETIC_STATUS_TONE.idle,
    statusText: '数据稳定',
  },
  settings: {
    badge: '系统主控台',
    title: '系统设置',
    subtitle: '全局风控、交易所连通性、通知与环境参数配置',
    statusTone: KINETIC_STATUS_TONE.stable,
    statusText: '连接状态良好',
  },
};

function buildPageChromeConfig(pageKey) {
  return (
    PAGE_CHROME[pageKey] || {
      badge: '控制台',
      title: '控制台',
      subtitle: '实时监控与策略执行面板',
      statusTone: KINETIC_STATUS_TONE.idle,
      statusText: '等待数据',
    }
  );
}

const KINETIC_ANTD_THEME = {
  token: {
    colorPrimary: KINETIC_THEME_TOKENS.colors.primary,
    colorInfo: KINETIC_THEME_TOKENS.colors.primary,
    colorSuccess: KINETIC_THEME_TOKENS.colors.tertiaryDim,
    colorWarning: '#d9b169',
    colorError: KINETIC_THEME_TOKENS.colors.error,
    colorText: KINETIC_THEME_TOKENS.colors.textOnSurface,
    colorTextSecondary: KINETIC_THEME_TOKENS.colors.textOnSurfaceVariant,
    colorBgBase: KINETIC_THEME_TOKENS.colors.background,
    colorBgContainer: KINETIC_THEME_TOKENS.colors.surfaceContainerLow,
    colorBorder: KINETIC_THEME_TOKENS.colors.outlineVariant,
    colorSplit: KINETIC_THEME_TOKENS.colors.outlineVariant,
    borderRadius: KINETIC_THEME_TOKENS.radius.md,
    fontFamily: KINETIC_THEME_TOKENS.fonts.body,
    boxShadow: KINETIC_THEME_TOKENS.shadows.soft,
  },
  components: {
    Layout: {
      bodyBg: KINETIC_THEME_TOKENS.colors.background,
      headerBg: KINETIC_THEME_TOKENS.colors.surface,
      siderBg: KINETIC_THEME_TOKENS.colors.surfaceContainerLow,
      triggerBg: KINETIC_THEME_TOKENS.colors.surfaceContainer,
    },
    Card: {
      headerBg: KINETIC_THEME_TOKENS.colors.surfaceContainerHigh,
      colorBgContainer: KINETIC_THEME_TOKENS.colors.surfaceContainerLow,
    },
    Table: {
      headerBg: KINETIC_THEME_TOKENS.colors.surfaceContainerHigh,
      headerColor: KINETIC_THEME_TOKENS.colors.textOnSurface,
      rowHoverBg: 'rgba(123, 208, 255, 0.09)',
      borderColor: KINETIC_THEME_TOKENS.colors.outlineVariant,
    },
    Input: {
      colorBgContainer: 'rgba(0, 34, 90, 0.35)',
      colorBorder: 'transparent',
      colorText: KINETIC_THEME_TOKENS.colors.textOnSurface,
      hoverBorderColor: KINETIC_THEME_TOKENS.colors.primary,
      activeBorderColor: KINETIC_THEME_TOKENS.colors.primary,
      activeShadow: '0 2px 0 0 rgba(123, 208, 255, 0.25)',
      borderRadius: 0,
    },
    Select: {
      colorBgContainer: KINETIC_THEME_TOKENS.colors.surfaceContainerHighest,
      colorBorder: KINETIC_THEME_TOKENS.colors.outline,
      optionSelectedBg: 'rgba(123, 208, 255, 0.14)',
      optionActiveBg: 'rgba(123, 208, 255, 0.1)',
      colorIcon: KINETIC_THEME_TOKENS.colors.primary,
    },
    Tag: {
      defaultBg: 'rgba(43, 70, 128, 0.18)',
      defaultColor: KINETIC_THEME_TOKENS.colors.textOnSurfaceVariant,
      borderRadiusSM: 2,
    },
    Tabs: {
      cardBg: KINETIC_THEME_TOKENS.colors.surfaceContainerLow,
      itemColor: KINETIC_THEME_TOKENS.colors.textOnSurfaceVariant,
      itemSelectedColor: KINETIC_THEME_TOKENS.colors.primary,
      inkBarColor: KINETIC_THEME_TOKENS.colors.primary,
    },
    Modal: {
      contentBg: KINETIC_THEME_TOKENS.colors.surfaceContainerLow,
      headerBg: KINETIC_THEME_TOKENS.colors.surfaceContainerHigh,
      titleColor: KINETIC_THEME_TOKENS.colors.textOnSurface,
    },
    Drawer: {
      colorBgElevated: KINETIC_THEME_TOKENS.colors.surfaceContainerLow,
      colorBgMask: 'rgba(3, 8, 24, 0.62)',
    },
  },
};

module.exports = {
  KINETIC_THEME_TOKENS,
  KINETIC_STATUS_TONE,
  KINETIC_ANTD_THEME,
  buildPageChromeConfig,
};
