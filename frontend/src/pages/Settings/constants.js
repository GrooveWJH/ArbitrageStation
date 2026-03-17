export const RULE_TYPE_OPTIONS = [
  { label: '亏损百分比触发 (%)', value: 'loss_pct' },
  { label: '单仓最大金额 (USDT)', value: 'max_position_usd' },
  { label: '总敞口上限 (USDT)', value: 'max_exposure_usd' },
  { label: '最小费率差要求 (%)', value: 'min_rate_diff' },
  { label: '最大杠杆倍数', value: 'max_leverage' },
];

export const ACTION_OPTIONS = [
  { label: '立即平仓', value: 'close_position' },
  { label: '仅告警不平仓', value: 'alert_only' },
];
